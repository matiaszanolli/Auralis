# Frontend Audit — 2026-10-22

**Scope**: `auralis-web/frontend/` (components, contexts, store, hooks, services, types, design system/theme/styles, a11y, tests, config).
**HEAD**: `44e4d433`. This is a fresh read of the live tree. 108 frontend commits have landed since the 2026-10-16 audit, mostly the #5840/#5841 split waves and the #5800/#5789/#5823 consolidations.
**Method**: nine dimension agents (`general-purpose`, sonnet, depth `deep`, at most 3 at once). Their outputs were merged and deduplicated across dimensions. The orchestrator re-verified every HIGH and several MEDIUM claims against the code. Findings were deduplicated against all 5,613 GitHub issues (open and closed, up to #5859) and the prior frontend reports.
**Tooling run**: `pnpm run type-check` is clean (0 errors). No full test-suite run. Single spec files and a few directory batches were run against the local install. That install is stale (jsdom 27.3.0 is installed, `package.json` requires ^30.1.0), so CI-only failures do not reproduce locally. The CI state was read from the `frontend-test.yml` run artifacts.

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 33 |
| LOW | 51 |
| **Total** | **87** |

All findings are NEW, except four reported as a **Regression of** a closed issue:
- HK-01: regression of #2259.
- DS-01 and DS-05: siblings that the #5641 fix never migrated.
- DS-10: regression of #4466.

Thirty-plus open issues that dimensions re-encountered are listed under *Existing (skipped)* and are not counted.

### Key themes

1. **Playback position and queue bookkeeping drift away from what is actually playing.**
   - A seek zeroes the engine clock: HK-01, a HIGH regression.
   - The engine's stale duration overwrites the playing track's duration: RDX-02.
   - A second `usePlaybackQueue()` mount re-applies the raw engine pointer: RDX-03.
   - Removing the playing queue item makes Next skip a track: RDX-04.
   - The library reads a Redux `isPlaying` flag that the local session never writes: RDX-01.
   - Several of these feed `useAutoAdvance`, so the user-visible effects are early cut-offs, missed advances and play/pause buttons in the wrong state.
2. **Navigation surfaces that render the wrong data.**
   - A playlist click shows the whole library under "Songs": CMP-01, HIGH.
   - The artist "All Tracks" tab is always empty and Play All does nothing: CMP-02.
   - Top-bar search only filters pages already loaded: CMP-03.
   - The album Year/Era sorts reorder only the pages loaded so far: CMP-04.
   - A failed fetch renders as "library empty": CMP-06.
   - A failed next-page load blanks the loaded list: CMP-07.
3. **The stream-session lifecycle acts on frames from a stream the user has already left.**
   - End and error frames for a superseded track tear down the new track: RDX-05.
   - `lastStreamCommand` is never cleared, so a reconnect can restart a finished or failed track unprompted: HK-04.
   - A retired WebSocket is never re-armed, and the UI offers no reconnect: HK-03 and A11Y-02.
   - The `PlaybackControlsContext` value changes on every 10 Hz tick, which undoes #5006: HK-02.
4. **The CI test gate has been red on every run since 2026-10-10.** TEST-01 counts 58 unbaselined failures in the latest run.
   - 37 of them are a jsdom 30 / MUI FocusTrap incompatibility.
   - 21 come from the #5601 selector change breaking `usePlaybackQueue.test.ts` (TEST-02).
   - The split waves have shipped with no working ratchet.
5. **Light mode is still incomplete after #5641.**
   - `surfaceRaised === surfacePrimary` makes scrollbars, slider rails, switch tracks and skeletons invisible: DS-02.
   - The MediaCard badge is unreadable: DS-01.
   - Residual white-alpha fills: DS-05.
   - Global `@keyframes pulse` name collisions that depend on mount order: DS-03.
6. **Accessibility gaps in the most-used keyboard paths.**
   - Context-menu events bubble through the React tree into the listbox: A11Y-01.
   - Drilling into album/artist detail moves no focus and announces nothing: A11Y-03.
   - The queue has no arrow-key navigation (A11Y-04), and removing a row loses focus (A11Y-05).
   - Focus rings are invisible on the volume control (A11Y-06) and on SegmentedControl (A11Y-07).
   - Dimmed rows fall below AA while any track plays: A11Y-08.

### Most impactful issues

- **HK-01 (HIGH)**: after any seek the clock restarts at 0:00. Because the clock ends early, the queue never auto-advances, and Play/Pause misbehaves once the audio ends.
- **CMP-01 (HIGH)**: playlists cannot be viewed from the UI. Clicking one shows the entire library under "Songs".
- **TEST-01 (HIGH)**: the frontend ratchet is permanently red, so new regressions cannot be told apart from the standing 58.
- **RDX-02 / RDX-04 / RDX-03**: each can make auto-advance skip a track, cut a track off early, or snap the queue highlight to the wrong track.
- **HK-04**: after an error or the end of the queue, a WebSocket reconnect can restart playback with no user action.

## Findings

Each finding keeps the ID its dimension agent assigned (CMP = components, RDX = Redux, HK = hooks, TS = types, DS = design system, API = API client, PERF = performance, A11Y = accessibility, TEST = tests). Where two dimensions reported the same defect, the entry has a **Merged** line naming the dropped duplicate.

## Critical (0)

None.

## High (3)

### CMP-01: Selecting a playlist in the sidebar routes to a view that does not exist and shows the whole library under "Songs"
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/layouts/Sidebar/SidebarContent.tsx:62-64`, `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:57-60,78,190`, `auralis-web/frontend/src/hooks/library/libraryPageFetch.ts:34-38`, `auralis-web/frontend/src/components/playlist/usePlaylistOperations.ts:31-34`, `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:156-160`
- **Status**: NEW (sibling of closed #5620, which only removed the `recent`/`playlists` entries)
- **Description**: `PlaylistList.onPlaylistSelect` calls `onItemClick('playlist-<id>')`, which flows through `useSidebarState.handleItemClick` -> `onNavigate` -> `ComfortableApp.setCurrentView('playlist-<id>')`. Nothing consumes a `playlist-N` view: `CozyLibraryView` only special-cases `albums`/`artists` (router) and `favourites` (endpoint). For `playlist-N` it falls through to `VIEW_CONFIG.songs` and `tracksEndpoint()` returns `/api/library/tracks`, i.e. the entire library. No playlist detail component exists (`grep PlaylistView|PlaylistDetail` is empty). The only mentions of the route are comments claiming it works (`useAppShortcuts.ts:159` "picking one routes to the playlist-N view", `ComfortableApp.tsx:49`).
- **Evidence**:
  ```ts
  // SidebarContent.tsx:64
  onPlaylistSelect={(playlistId) => onItemClick(`playlist-${playlistId}`)}
  // libraryPageFetch.ts:35  (no playlist branch)
  return view === 'favourites' ? `/api/library/tracks/favorites?...` : `/api/library/tracks?...`
  // usePlaylistOperations.ts:34  deleting the selected playlist navigates to 'playlist--1'
  onPlaylistSelect(-1);
  ```
- **Impact**: Clicking any playlist highlights it in the sidebar but shows every track under the heading "Songs". A playlist's contents can never be viewed from the UI. After deleting the selected playlist the app navigates to the bogus view `playlist--1`. Bulk actions in that mislabelled view act on library tracks as if they were playlist members.
- **Siblings**: `useAppDragDrop.ts:68-94` (drop targets use `playlist-N` droppable ids - unaffected, different namespace).
- **Related**: #5620 (closed), CMP-10.
- **Suggested Fix**: Add a playlist detail view (fetch `/api/playlists/{id}` tracks) routed from `CozyLibraryView`/`LibraryViewRouter` on `view.startsWith('playlist-')`, or stop navigating on playlist click until one exists. Make the delete path navigate to `songs`, not `playlist--1`.

### HK-01: Seek offset is never applied, so playback position restarts at 0:00 after every seek
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:94-107` (early return) vs `:170-172` (the only `setSeekOffset` call); `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:68-69`; `auralis-web/frontend/src/services/audio/PlaybackPositionTracker.ts:70-90`
- **Status**: Regression of #2259 (the #2259 `setSeekOffset` fix is still in the file but became unreachable for ordinary seeks when #3185 added the resume guard)
- **Description**: `seekTo` keeps the live engine and buffer. It calls `engine.stopPlayback()` and `pcmBuffer.reset()`, then sends `seek`. The backend answers with `audio_stream_start {is_seek: true, seek_position}`. `handleStreamStart` takes the "resume guard" branch because `isSeek && engine && buffer`, and returns before reaching `engine.setSeekOffset(seekPosition)`. `engine.stopPlayback()` has already called `positionTracker.reset()`, which zeroes `seekOffsetSeconds`. When the new chunks start the engine, `getCurrentPlaybackTime()` is `0 + samplesPlayed/sampleRate`, i.e. time since the seek rather than track time. `setSeekOffset` is only reached when the engine or buffer is null (for example after an error cleanup). The guard was added in #3185 after the #2259 offset fix and made it dead for ordinary seeks. No test covers it: `usePlayEnhanced.test.ts:1148` fires `is_seek` against a mocked engine and never asserts the offset.
- **Evidence**:
```ts
if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) {
  ...                       // totalChunks/processedChunks reset only
  return;                   // <- skips engine.setSeekOffset(seekPosition) at line 171
}
```
- **Impact**: After any seek to S in a track of duration D:
  - The time display and progress bar jump to 0:00 and count up from there.
  - `useAutoAdvance` (`usePlaybackSessionHooks.ts:120`) requires `currentTime >= trackDuration - 0.5`. The engine's clock ends at D-S, so the track ends silently and the queue never advances.
  - `PlaybackSessionContext.tsx:91` (`playbackEnded`) never becomes true, so `isPlaybackActive` stays true after the audio has ended. Play/Pause then toggles pause/resume instead of restarting the track.
  - The reconnect resume getter (`usePlaybackTransport` `getPosition`) reports the same wrong position, so a WS drop after a seek resumes from the wrong place.
- **Siblings**: The reconnect and `reissueActiveStreamAs` paths also enter the guard, but they never stop the engine, so their offset survives. Only the seek path loses it.
- **Related**: #2259 (closed, original offset fix), #3185 (closed, introduced the guard), #5673 (open, no tests pin HIGH hook defects).
- **Suggested Fix**: In the guard branch, call `core.playbackEngineRef.current.setSeekOffset(seekPosition)` when `isSeek && seekPosition > 0`, before chunks restart the engine. Alternatively make `AudioPlaybackEngine.stopPlayback` preserve the offset and add a spec asserting position continuity across seek.
- **Merged**: The Performance dimension found the same defect independently (PERF-01) and adds: the cleanest fix is `engine.setSeekOffset(position)` in `useEnhancedSeek.seekTo` right after `stopPlayback()`; do not reset the offset on the reconnect-resume path, where the engine keeps playing.

### TEST-01: Frontend CI ratchet has been red since 2026-10-17 — 58 unbaselined failures, 37 of them a jsdom 30 / MUI FocusTrap incompatibility that local runs cannot reproduce
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/package.json` (`"jsdom": "^30.1.0"`, bumped in a800893e 2026-09-17); `auralis-web/frontend/test-baseline.json`; `.github/workflows/frontend-test.yml`; failing specs in the list below
- **Status**: NEW (adjacent to #5679, which is about the missing test-count floor, not about the gate being permanently red)
- **Description**: `frontend-test.yml` has failed on every run from 2026-10-10 onward (all 26 sampled runs, 24 of them since 2026-10-17); the last green run was 2026-09-17 19:45Z. The latest run reports `Vitest: 3149 passed, 154 failed (baseline allows 96)`, `58 NEW test failure(s) not in the baseline`, and `--strict-stale: 1 baselined test(s) now pass`. CI resolves jsdom 30.1.0 (`jsdom@30.1.0` appears in the install log). The baseline was generated against jsdom 27.3.0 locally (installed `node_modules/jsdom` is 27.3.0), so every Dialog/Menu/Modal spec that unmounts a MUI Modal after a focus move throws in CI only. The 58 unbaselined failures from the CI artifact, by cause:
  - 37 x `TypeError: nodeToRestore.current.focus is not a function` thrown from `@mui/material/Unstable_TrapFocus/FocusTrap.mjs:141` (restore-focus on unmount; `nodeToRestore` is the focus event's `relatedTarget`). Files: SimilarTracksModal.test.tsx 13, AddToPlaylistMenu.test.tsx 7, SettingsDialog.test.tsx 5, ArtistInfoModal.test.tsx 4, PlaylistList.test.tsx 3, a11y.spec.tsx 2, EditMetadataDialog.staleCloseTimer.test.tsx 1, CozyArtistList.rowRenders.test.tsx 1. All of these pass locally under jsdom 27.
  - 21 x usePlaybackQueue.test.ts (see TEST-02).
  - 1 x TextDisabledContrast (TEST-03).
  - 1 x CozyAlbumGrid "should fetch albums on mount" (TEST-04).
  - Plus 1 stale baseline entry: `ProgressBar Click to Seek should call onSeek when clicked at midpoint` now passes in CI, which fails `--strict-stale`.
  The CI-only portion was not reproduced locally because the audit machine has jsdom 27; the jsdom 30 attribution rests on (a) the identical MUI 9.0.1 locally and in CI, (b) the only environment difference found being jsdom 27.3.0 vs 30.1.0, and (c) the last green run (a59e77de, 2026-09-17 19:45Z) preceding the jsdom bump commit a800893e (23:13Z, first red). CLAUDE.md says to generate the baseline from a CI artifact; the checked-in baseline (totalTests 3349) was evidently not.
- **Evidence**:
  ```
  FocusTrap.mjs:139-142  if (!disableRestoreFocus && nodeToRestore.current) {
                           ignoreNextEnforceFocus.current = true;
                           nodeToRestore.current.focus();      // TypeError under jsdom 30
  frontend-test.yml log: ✖ 58 NEW test failure(s) not in the baseline  /  --strict-stale: 1 baselined test(s) now pass
  ```
- **Impact**: With the gate permanently red, a genuinely new regression in any of the 108 recent frontend commits (including the #5840/#5841 split waves) is indistinguishable from the standing 58, and the "baseline may shrink, never grow" contract is unenforceable. Developers working from a stale `node_modules` see green locally. Nothing breaks at runtime.
- **Siblings**: the same local-vs-CI drift applies to `pnpm run test:baseline:update` (it is only valid when run on the CI dependency set).
- **Related**: #5679 (ratchet has no count floor), #5681 (harness drift); TEST-02, TEST-03, TEST-04.
- **Suggested Fix**: Make the FocusTrap restore a no-op under jsdom 30 (global shim in `src/test/setup.ts`, or `disableRestoreFocus` in the shared test wrapper) or pin jsdom to a compatible version, then regenerate the baseline from a CI artifact. Add a CI step (or a pre-commit check) that fails when installed jsdom/vitest differ from the lockfile.


## Medium (33)

### CMP-02: Artist detail "All Tracks" tab is always empty and Play All / Shuffle are no-ops
- **Severity**: MEDIUM (dimension agent rated HIGH; downgraded at merge: the artist's tracks remain playable via the Albums tab and the artist context menu, so a workaround exists)
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Details/useArtistDetailsData.ts:55-63`, `auralis-web/frontend/src/components/library/Details/ArtistDetailView.tsx:41-53`, `auralis-web/frontend/src/components/library/Details/ArtistDetailTabs.tsx` (tab label + `TracksTab`)
- **Status**: NEW
- **Description**: `useArtistDetailsData` builds the artist with a hard-coded `tracks: []`. The `GET /api/artists/{id}` response carries albums and counts only (`ArtistDetailApiResponse` has no `tracks`). The tracks endpoint (`ENDPOINTS.ARTIST_TRACKS`, `libraryService.getArtistTracks`) is only called from the context-menu hook, never from the detail view. Everything in `ArtistDetailView` that reads `artist.tracks` therefore sees an empty array.
- **Evidence**:
  ```ts
  // useArtistDetailsData.ts:55-63
  const artistData: Artist = { ...base, albums: (...), tracks: [] };
  // ArtistDetailView.tsx:41-45
  const handlePlayAll = () => { if (artist?.tracks && artist.tracks.length > 0) { playTrack(artist.tracks[0]); } };
  // ArtistDetailTabs: <Tab label={`All Tracks (${artist.tracks?.length || 0})`} .../>
  ```
- **Impact**: The "All Tracks (0)" tab always shows "No tracks found for this artist" for every artist. The prominent "Play All" and "Shuffle" buttons in `ArtistHeader` do nothing (guarded by the length check, so no error, just silence). Even with data, "Play All" would start only the first track (same pattern as `AlbumDetailView.handlePlayAlbum`).
- **Siblings**: `AlbumDetailView.handlePlayAlbum` plays only `tracks[0]` and does not queue the rest (`AlbumDetailView.tsx:71-75`).
- **Related**: #5612 (closed; fixed the context-menu "Play All" only).
- **Suggested Fix**: Fetch `getArtistTracks(artistId, signal)` alongside the detail request (or lazily when the tab opens) and map through `transformTracks`; route Play All/Shuffle through the queue-setting path the context menu uses.

### CMP-03: Top-bar search only filters already-loaded track pages, and is ignored entirely on Albums/Artists
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:81-91`, `auralis-web/frontend/src/components/library/Views/TrackListView.tsx:94-100`, `auralis-web/frontend/src/components/core/AppTopBarSearchInput.tsx:46`, `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:36-47`
- **Status**: NEW
- **Description**: `searchQuery` is consumed in exactly one place: a client-side `tracks.filter(...)` over whatever pages `useLibraryPagination` has loaded (`PAGE_LIMIT = 50`). It is never sent to the backend (`useInfiniteAlbums` supports `search` but `CozyAlbumGrid` calls it with only `{limit: 50}`; the working backend-search UI, `SearchBar.tsx`/`useSearchLogic.ts`, is unmounted). `LibraryViewRouter` has no `searchQuery` prop, so on Albums/Artists/detail views the field accepts input and does nothing. In grid mode (the default `viewMode`) the filtered list is usually shorter than the viewport, so `InfiniteScroll` never fires `next` and the remaining pages are never fetched.
- **Evidence**:
  ```tsx
  // AppTopBarSearchInput.tsx:46
  placeholder="Search tracks, albums, artists..."
  // CozyLibraryView.tsx:84-90  (only consumer)
  return tracks.filter(track => track.title.toLowerCase().includes(searchQuery.toLowerCase()) || ...)
  ```
- **Impact**: In a library of more than 50 tracks, searching for an artist/title in Songs/Favourites returns only the matches among the first loaded pages, or shows "No tracks match..." while matches exist further down. On Albums/Artists, typing does nothing. The placeholder advertises albums and artists search.
- **Siblings**: `SearchResultsAnnouncement` announces the (partial) count as if it were the total.
- **Related**: closed #2643 (old search hook), #5668.
- **Suggested Fix**: Pass `searchQuery` into `useLibraryPagination` (the tracks endpoint already supports search) and into `useInfiniteAlbums`/`useArtistsQuery` (`search` option exists), debounced; or scope the placeholder and field to the views that actually filter.

### CMP-04: Albums "Year" and "Era" sorts only reorder the loaded pages; the backend `order_by` is never used
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:66,78-99`, `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:24-53`
- **Status**: NEW
- **Description**: The sort selector sorts the flattened infinite-query pages in memory. The server returns albums in `title` order (default `order_by='title'`, supported values `title|year|created_at`) 50 at a time, and `fetchAlbums` never passes `order_by`. "Year" therefore shows the newest of the first 50 alphabetical albums; each additional page appended on scroll is re-sorted into the already-visible grid, so cards jump around. "Era" grouping likewise groups only what has loaded. "A-Z" uses `localeCompare` over the loaded subset, which can disagree with the SQL title collation near page boundaries.
- **Evidence**:
  ```ts
  // CozyAlbumGrid.tsx:66   useInfiniteAlbums({ limit: 50 })   // no orderBy
  // CozyAlbumGrid.tsx:90   sorted.sort((a, b) => (b.year || 0) - (a.year || 0));
  ```
- **Impact**: "Sort by Year / Era" is wrong for any library with more than one page of albums and visibly reshuffles while scrolling.
- **Siblings**: none.
- **Suggested Fix**: Add `orderBy` to the `useInfiniteAlbums` query key and request (`order_by=year` etc.) and drop the client-side re-sort; keep era grouping over server-ordered pages.

### CMP-05: Track selection survives view and search changes, so bulk actions can hit tracks the user cannot see
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/hooks/library/useTrackSelection.ts:42-45`, `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:93-103,231-236`, `auralis-web/frontend/src/components/library/useBatchOperations.ts:94-168`, `auralis-web/frontend/src/components/CozyLibraryView/useLibraryKeyboardShortcuts.ts:35-46`
- **Status**: NEW
- **Description**: `CozyLibraryView` is one mounted instance across `songs`/`favourites`/`albums`/`artists` (only the `view` prop changes), and `useTrackSelection` has no reset on view change and no pruning against the visible list. `useLibraryKeyboardShortcuts` is also active in every view, so Ctrl/Cmd+A in Albums/Artists (where `tracks` is still loaded) calls `preventDefault()` and silently selects every track. Selection also persists while a search narrows the list. `BatchActionsToolbar` then shows the stale count, and `handleBulkRemove`/`handleBulkToggleFavorite`/`handleBulkAddToPlaylist` operate on `Array.from(selectedTracks)`.
- **Evidence**:
  ```ts
  // useTrackSelection: state only ever mutated by toggle/selectAll/clear
  const [selectedTracks, setSelectedTracks] = useState<Set<number>>(new Set());
  // useBatchOperations.handleBulkRemove
  const trackIds = Array.from(selectedTracks);  // un-favourites ids that may not be on screen
  ```
- **Impact**: Select tracks in Songs, switch to Favourites: the toolbar shows "N selected" and "Remove" un-favourites those (possibly invisible) tracks after a confirm that counts hidden items. Select all, type a search, press "Add to playlist": hidden tracks are added too. Ctrl+A on the Albums page selects everything with no feedback and the selection reappears on return to Songs.
- **Siblings**: `handleBulkToggleFavorite` builds `favoriteById` from the current `tracks`; ids from a previous view are absent and get POSTed as "set favourite" instead of toggled.
- **Suggested Fix**: Clear selection when `view` changes (key the selection on view) and intersect `selectedTracks` with `filteredTracks` ids before any bulk operation and when computing `selectedCount`; only register the Ctrl+A handler when the track list is the rendered view.

### CMP-06: A failed track fetch renders as "Your library is empty - scan a folder"
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:70-79,218-232`, `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:105-125`
- **Status**: NEW
- **Description**: `useLibraryWithStats` returns `error`, but `CozyLibraryView` never destructures it. When the first page fails, the pagination hook clears `tracks`, sets `error`, shows a transient toast and sets `loading=false`. The view then satisfies `filteredTracks.length === 0 && !loading` and renders `LibraryEmptyContent`, whose fallthrough branch is `EmptyLibrary` (with a DropZone "Drop a music folder here"). In favourites, the same path shows "No favorites yet".
- **Evidence**:
  ```tsx
  // CozyLibraryView.tsx:70-79 destructures tracks, loading, scanning, ... (no `error`)
  {filteredTracks.length === 0 && !loading ? (<LibraryEmptyContent .../>) : (...)}
  ```
- **Impact**: After a backend hiccup or a timeout the persistent UI tells the user their library is empty and prompts them to rescan, while the only error signal is a toast that disappears. There is no retry control.
- **Siblings**: `CozyArtistList`/`CozyAlbumGrid` do show an error, but see CMP-07.
- **Suggested Fix**: Destructure `error`, render an error state with a Retry button (calling `fetchTracks()`) when `error && tracks.length === 0`, before the empty-library branch.

### CMP-07: A failed "next page" replaces the whole loaded Albums/Artists list with an error and no way to retry
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:106-112`, `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:95-97`, `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:221-225`, `auralis-web/frontend/src/components/library/Items/artists/ArtistListEmptyState.tsx`
- **Status**: NEW
- **Description**: Both lists branch on `error` before checking whether data is already on screen. `useInfiniteQuery` keeps `data` and sets `error` when `fetchNextPage` fails; `useLibraryQuery.fetchMore` likewise calls `setError(result.error)` and leaves `data` intact. The components then return only the error `EmptyState` ("Error Loading Albums" / "Error Loading Artists"), discarding the rendered pages. Neither error state offers a retry action (no `actionLabel`/`onAction`), and `EmptyState` is a `role="status"` region, not an alert.
- **Evidence**:
  ```tsx
  // CozyAlbumGrid.tsx:107
  if (error) { return (<EmptyState title="Error Loading Albums" description={error.message || 'Failed to load albums'} />); }
  // CozyArtistList.tsx:95
  if (error || artists.length === 0) { return emptyState; }
  ```
- **Impact**: One transient failure while scrolling an already-loaded library blanks the grid/list, losing scroll position, with no in-place recovery (the user must switch views). Same dead-end on an initial load failure.
- **Siblings**: `ArtistDetailView` error state (CMP-12).
- **Suggested Fix**: Show the full-page error only when there is no data (`error && albums.length === 0`); otherwise keep the list and show an inline "Failed to load more - Retry" row wired to `fetchNextPage`/`fetchMore`. Pass an `actionLabel`/`onAction` retry to the empty-state error variants.

### CMP-08: Empty-library DropZone wires both drop and click to a handler that ignores the path and opens a second folder picker
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/CozyLibraryView/LibraryEmptyContent.tsx:32`, `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:28,62-85`, `auralis-web/frontend/src/components/shared/DropZone/DropZone.tsx:58-71`, `auralis-web/frontend/src/components/shared/DropZone/useDropZone.ts:88-92`
- **Status**: NEW
- **Description**: `LibraryEmptyContent` passes the zero-argument `handleScanFolder` as both `onFolderDrop` and `onFolderSelect`. `DropZone.handleClick` opens the Electron folder picker itself and then calls `onFolderSelect(path)`; `handleScanFolder` ignores its argument and calls `selectFolder()` again. For a drop, `onFolderDrop(path)` also ignores the dropped path and opens the picker. The path DropZone extracts for a drop is `entry.fullPath` (a drop-root-relative `"/FolderName"`, not an absolute path), so it could not be used as-is anyway.
- **Evidence**:
  ```tsx
  // LibraryEmptyContent.tsx:32
  <EmptyLibrary onScanFolder={onScanFolder} onFolderDrop={onScanFolder} scanning={scanning} />
  // useLibraryScan.ts:28   handleScanFolder: () => Promise<void>   // takes no folder
  ```
- **Impact**: First-run flow: clicking the drop zone makes the user choose a folder twice (the first choice is discarded); dropping a folder never scans it and instead pops a picker.
- **Siblings**: `LibraryEmptyState.tsx` (orphan) passes only `onScanFolder`.
- **Suggested Fix**: Give `handleScanFolder` an optional `folderPath` parameter that skips the picker when provided; in Electron, resolve dropped files with `webUtils.getPathForFile`/`File.path` rather than `fullPath`.

### CMP-09: Escape clears the app's search state but not the visible search field
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:175-186`, `auralis-web/frontend/src/components/core/useSearchInput.ts:19-45`, `auralis-web/frontend/src/components/core/AppTopBar.tsx:107-116`
- **Status**: NEW
- **Description**: The text in the top-bar field is `useSearchInput`'s private `useState`; `ComfortableApp` owns a separate `searchQuery` that receives debounced values via `onSearch`. The `Escape` shortcut calls `setSearchQuery('')` on the parent state only. `keyboardShortcutsService.handleKeyDown` returns early for input targets, so Escape only fires while focus is outside the field - exactly the case where the field still shows the old text. `AppTopBar` takes no value prop, so the parent cannot reset it.
- **Evidence**:
  ```ts
  // useAppShortcuts.ts:180
  if (searchQuery) { setSearchQuery('');  info('Search cleared'); }
  // useSearchInput.ts:20   const [searchQuery, setSearchQuery] = useState('');   // independent copy
  ```
- **Impact**: User presses Esc, sees "Search cleared" and the full list, yet the field still reads the old query; typing the same text again does not re-trigger anything visible, and the field and results disagree.
- **Siblings**: `onSearchClear` in `ComfortableApp.tsx:159` only goes the other direction (field -> parent).
- **Suggested Fix**: Make the top-bar input controlled by the parent's `searchQuery` (keep the local debounce for the callback only), or expose a reset via a ref/prop.

### CMP-10: Sidebar keeps its own "selected item", which disagrees with the app's current view
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/layouts/Sidebar/useSidebarState.ts:18-35`, `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:127-155`, `auralis-web/frontend/src/components/library/useNavigationState.ts:11-18`
- **Status**: NEW
- **Description**: The active nav highlight comes from `useSidebarState.selectedItem` (local, initial `'songs'`), while the view comes from `ComfortableApp.currentView`. Shortcuts `1`/`2`/`3` call `setCurrentView` directly, so the highlight stays on the old item. `AppSidebar` swaps `Sidebar` <-> `MobileSidebarDrawer` on a media-query change; each remount resets `selectedItem` to `'songs'` regardless of the view. Separately, clicking the sidebar item for the view you are already in is a no-op: `currentView` does not change, so `useNavigationState`'s reset-on-view-change never runs and an open album/artist detail page stays.
- **Evidence**:
  ```ts
  const [selectedItem, setSelectedItem] = useState('songs');   // not derived from currentView
  // useAppShortcuts: setCurrentView('albums') -- Sidebar highlight unchanged
  ```
- **Impact**: After pressing `2`, the Albums view is shown with "Songs" highlighted. In an album detail page, clicking "Albums" in the sidebar does not return to the grid.
- **Siblings**: `CollapsedSidebar` takes no selection prop (no highlight in collapsed mode).
- **Related**: CMP-01.
- **Suggested Fix**: Lift the selected view into `ComfortableApp` (single source of truth passed to `Sidebar`), and make same-view nav clear the album/artist selection (e.g. bump a nav-session key).

### RDX-01: Library "playing" state reads a Redux flag that the local playback session never writes
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/components/library/usePlaybackState.ts:28`, `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:74-158`, `auralis-web/frontend/src/store/slices/playerSlice.ts:60-70`
- **Status**: NEW
- **Description**: `player.isPlaying` is written only by backend traffic (`playback_started/resumed/paused/stopped` events and `player_state` snapshots, `hooks/player/usePlayerStateSync.ts:166-180`, `playerStateSnapshot.ts:64`). The browser session that actually plays audio never touches it: `pausePlayback`/`resumePlayback`/`stopPlayback` act on the local engine and `setIsPaused`, the frontend sends no pause/stop message at all (only `play_enhanced`/`play_normal`), and the `usePlayerActions().play/pause` wrappers that do dispatch it have no production caller. Yet the library treats Redux `isPlaying` as "single source of truth for playback state" (`usePlaybackState`) and feeds it to the rows and the album play button. The transport bar is correct only because `Player` derives its own `isStreaming && !isPaused`.
- **Evidence**:
  ```ts
  // usePlaybackState.ts
  const isPlaying = useSelector(selectIsPlaying);          // backend-driven
  // TrackRowPlayButton.tsx:25,30
  const action = isCurrent && isPlaying ? 'Pause' : 'Play';
  // usePlaybackTransport.ts:77-82 -- local pause, no dispatch, no WS message
  const pausePlayback = useCallback(() => { pauseHoldRef.current = true;
    playbackEngineRef.current?.pausePlayback(); setIsPaused(true); }, ...);
  ```
- **Impact**: After the user pauses from the transport bar (or after the track ends), `playback_started` from the queue POST has left `isPlaying === true`, so the current library row / album header keep showing the Pause icon and "playing" styling. Clicking that "Pause" button calls the session's `handlePlayPause`, which toggles, so it resumes playback. Same flag also gates the 10 Hz engine-time tick and drives a pause/resume effect in `usePlaybackTransport` (lines 121-158): if a backend snapshot ever sets `is_playing:false` (queue clear, backend restart) and the user then resumes locally, `isPlaying` stays false, the tick never runs and the progress bar freezes while audio plays.
- **Siblings**: `components/library/Views/TracksTab.tsx:31`, `components/library/Items/tables/AlbumTrackTable.tsx:33`, `components/library/Details/AlbumHeaderActions.tsx:51` (+ `AlbumActionButtons.tsx:46,77`), `components/library/CozyLibraryView.tsx:120`, `components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:75`, `hooks/audio/useAudioVisualization.ts:37`.
- **Related**: #5603 (transport side fixed), #5514, #2988 (same class on `stop()`), `docs/audits/AUDIT_FRONTEND_2026-10-16.md` Player siblings note. No open issue covers the library-side consumers.
- **Suggested Fix**: Make the session the writer: dispatch `setIsPlaying` from the session's pause/resume/stop/stream-end/error paths (or expose a derived `isActivelyPlaying` from `PlaybackControlsContext` and have `usePlaybackState` read that). Then stop gating the engine tick and pause effect on the backend-fed flag.

### RDX-02: #5601 stale-engine gate leaves `duration` ungated, so the engine's old duration overwrites the playing track's duration
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/playerStateSnapshot.ts:51-80`, `auralis-web/frontend/src/store/slices/playerQueueSync.ts:111-116`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:90-91`
- **Status**: NEW (sibling of closed #5601, which gated only `current_track` and `queue_index`)
- **Description**: When a snapshot's `current_track` differs from the locally playing track, the code keeps the local track but still applies the snapshot's `duration` through `setDurationAndSyncQueue`. That thunk writes `player.currentTrack.duration` (reducer `setDuration`) and every `queue.tracks` entry with the playing track's id. The comment calls the staleness "self-limiting", but nothing re-syncs `currentTrack.duration` afterwards, and the engine pointer stays on the old track until the next play command (#5460).
- **Evidence**:
  ```ts
  if (track && playingTrackId != null && track.id !== playingTrackId) { /* keep local track */ }
  ...
  if ('duration' in state && typeof state.duration === 'number' && Number.isFinite(state.duration)) {
    dispatch(setDurationAndSyncQueue(state.duration));   // engine's (old) track duration
  }
  ```
  Backend pushes a full snapshot on every WS (re)connect (`backend/ws_handlers/connection.py:151-160`), and `PlayerState.duration` is the engine pointer track's duration.
- **Impact**: Skip locally from A (180 s) to B (300 s), then reconnect (sleep/wake, blip) or hit any broadcast carrying the stale pointer: B's `currentTrack.duration` becomes 180. `Player.tsx:128,149` (progress/time display) and `PlaybackSessionContext.tsx:90` (`trackDuration`) all read it, so `useAutoAdvance` (`nearEnd`, `streamingState === 'complete'`) advances at ~179.5 s, cutting B off 2 minutes early; the opposite sign gives a progress bar past 100% and no auto-advance. Redux `setCurrentTime` also clamps to the wrong duration.
- **Siblings**: `current_time` in the same snapshot (and `position_changed` ticks from the backend ticker, `usePlayerStateSync.ts:149`) are likewise the engine pointer track's position, written to `player.currentTime` (see RDX-09).
- **Related**: #5601, #5460 (open, backend half), #4580. There is no test of the track gate in `hooks/player/__tests__/usePlayerStateSync.test.ts`.
- **Suggested Fix**: Apply the same gate to `duration`/`current_time` (skip them when the snapshot's `current_track.id` differs from the local one), or never let a snapshot write `currentTrack.duration` unless the ids match. Add a spec for "stale engine track + different duration".

### RDX-03: A second `usePlaybackQueue()` mount re-runs the initial queue fetch and applies the raw engine index each time the sidebar remounts
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:28`, `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:169-174`, `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:52-67`
- **Status**: NEW
- **Description**: `usePlaybackQueue()` bundles side effects (`useQueueSubscription`, `useQueueFetch`, a new `useQueueMutations` instance); `QueuePanel.tsx`/`QueuePanelExpanded.tsx` document that it must be called once. `usePlaylistContextActions` calls it only to get `setQueue`. It is mounted from `PlaylistList` inside `SidebarContent`, which `Sidebar` unmounts whenever it collapses (`CollapsedSidebar` branch) and `MobileSidebarDrawer` remounts. Each mount issues `GET /api/player/queue` and dispatches `setQueue(...)` + `setCurrentIndex(response.current_index)` with the raw engine pointer, with none of the #5601 reconciliation `useQueueSubscription` and `applyPlayerStateSnapshot` apply.
- **Evidence**:
  ```ts
  const { setQueue } = usePlaybackQueue();        // usePlaylistContextActions.ts:28
  dispatch(reduxSetCurrentIndex(response.current_index ?? 0));   // useQueueFetch.ts:59, unreconciled
  ```
- **Impact**: After any local Next/Previous (engine pointer stale until the next play command), collapsing and re-expanding the sidebar snaps `queue.currentIndex` back to the old track: the queue highlight jumps, and the next Next/auto-advance continues from the wrong slot. It also doubles every `queue_changed` handler (two subscriptions) and starts two concurrent fetches at launch (the per-instance stale-GET guard in `useRestAPI` does not cover two instances).
- **Siblings**: none other (`QueuePanel` is the only intended owner).
- **Related**: #5601, #5460, #3925.
- **Suggested Fix**: Give `usePlaylistContextActions` the mutations only (e.g. export `useQueueMutations` and call it directly, or lift the fetch/subscription into one app-level mount), and run `reconcileQueueIndex` in `useQueueFetch` before dispatching the index.
- **Merged**: The Hook Correctness dimension found the same defect independently (HK-05) and adds: `useQueueSubscription` reads `playingTrackId`/`queueTracks` from render-captured values while `usePlayerStateSync` reads `store.getState()` at call time, so between a dispatch and the next render the queue handler sees the previous values.

### RDX-04: Removing the playing queue item leaves `queue.currentIndex` on the next track, so Next/auto-advance skips one
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:74-92`, `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:125-141`, `auralis-web/frontend/src/hooks/player/queueIndexReconciliation.ts:34-50`
- **Status**: NEW
- **Description**: `removeTrack(index === currentIndex)` keeps `currentIndex` unchanged (unless it was the last slot), so the index now designates the track that slid into the slot, while `player.currentTrack` and the client stream are still the removed track. `handleNext`/`useAutoAdvance` then take `currentIndex + 1`. The follow-up `queue_changed` does not repair it: `reconcileQueueIndex` returns `null` when the playing track is absent from the new queue ("keep the local index").
- **Evidence**:
  ```ts
  } else if (index === state.currentIndex && state.currentIndex >= state.tracks.length) {
    state.currentIndex = Math.max(0, state.currentIndex - 1);   // only the last-slot case moves it
  }
  // handleNext: let nextIndex = currentQueueIndex + 1;
  ```
- **Impact**: Queue [A, B, C], A playing at index 0. Delete A in the panel (Delete key or remove button on the current row is reachable: `QueueTrackItem.tsx:73-77`). Audio continues, the highlight moves to B, and when A ends auto-advance plays C; B is never played. The panel's highlight (`index === currentIndex`) also marks a track that is not playing.
- **Siblings**: none.
- **Related**: #2403 (backend side of removing the playing track).
- **Suggested Fix**: When the removed index is the playing slot and a successor exists, treat the stored index as "just before the successor" (store `currentIndex - 1` semantics via a `playingRemoved` marker) or have Next use the playing track's position/`currentIndex` without +1 in that case; at minimum make `reconcileQueueIndex` return the successor slot minus one.

### RDX-05: Reducers drop stale stream errors (#4434) but the handler side effects and the middleware still act on them
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:199-258`, `auralis-web/frontend/src/store/slices/playerStreamingReducers.ts:176-185`, `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:130-235`
- **Status**: NEW (overlaps the hooks dimension; reported here for the Redux guard split)
- **Description**: `setStreamingError` ignores an error whose `trackId` does not match the active stream ("a stale error from a superseded track after a rapid skip"), but (a) `handleStreamError` runs `cleanupStreaming()` and the `recovery_position` re-issue unconditionally, so a late `audio_stream_error` for the previous track disposes the new track's engine/buffer and may re-issue the old track's stream; `audio_stream_end` with `completed`/`errored` calls `markStreamEnded()` on the live engine the same way; (b) the middleware classifies from the action only, so an error the reducer discarded is still logged and, when its text matches the NETWORK heuristic, forwarded to `connection.lastError`.
- **Evidence**:
  ```ts
  dispatch(setStreamingError({ streamType, error: errorMsg, trackId: message.data.track_id })); // reducer may no-op
  cleanupStreaming();                                    // always runs
  ```
  `useStreamSubscriptions.ts` filters chunks by epoch but forwards `audio_stream_error` with no epoch/track check (`AudioStreamErrorMessage` carries only `track_id`).
- **Impact**: Trigger depends on the backend emitting an error/end for a superseded stream, which #4434 treats as real. When it happens after a rapid skip: playback of the new track goes silent with Redux still `buffering/streaming`, or a spurious "reconnecting" status (`lastError` set while `wsConnected` is never true, see #5615) until the next health poll.
- **Siblings**: `handleStreamEnd` `markStreamEnded()` (line 206); the `setStreamingError` sites without `trackId` (`useEnhancedStreamStart.ts:236`, `useEnhancedPlayCommand.ts:170`, `useStreamMessageHandlers.ts:182`) cannot be filtered at all.
- **Related**: #4434, #4430, #5615.
- **Suggested Fix**: Compare `message.data.track_id` with the active stream's track id (`streaming.enhanced.trackId` / `currentTrackInfoRef`) once in `handleStreamError`/`handleStreamEnd` and return early before any side effect; have the middleware ignore actions the reducer rejected (or forward from the reducer's resulting state change).
- **Merged**: The Hook Correctness dimension found the same defect independently (HK-06) and adds: `audio_stream_end`/`audio_stream_error` frames carry no `stream_epoch`, so the chunk path's epoch gate cannot be reused; adding `stream_epoch` to both frames is the robust fix.

### HK-02: `PlaybackControlsContext` value changes on every provider render, which defeats the #5006 split
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:149-157`; `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:155-174`; `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:76-82,186-189`; `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:115-145,147-173,242-261`
- **Status**: NEW (the fix for closed #5006 is incomplete)
- **Description**: `usePlayEnhanced` passes inline `onCleanupExtra` and `onDisconnectExtra` arrows in the options object, so they get a new identity every render. The chain from there:
  - `cleanupStreaming` is `useCallback(..., [closeContextOnCleanup, onCleanupExtra, ...])`, so it is new every render.
  - `stopPlayback` depends on `cleanupStreaming`, so it is new every render.
  - `handleNext` and `handlePrevious` list `stopPlayback` in their deps, so they are new every render.
  - `controlsValue` lists both in its `useMemo` deps, so it is rebuilt every render.
  - The provider re-renders on every `currentTime` tick (`core.currentTime` state, 10 Hz while playing) and on every progress dispatch.
- **Evidence**:
```ts
// usePlayEnhanced.ts
onCleanupExtra: () => { setIsSeeking(false); },        // new identity each render
// useAudioStreamingCore.ts
const cleanupStreaming = useCallback(..., [closeContextOnCleanup, onCleanupExtra, clearStreamStartWatchdog]);
```
- **Impact**: Every `usePlaybackControls()` consumer re-renders at about 10 Hz during playback. That includes `ComfortableApp` (the app root), `usePlayTrack` users and `usePlaylistContextActions`. The #5006 split was meant to stop exactly this, and `playbackSessionContexts.ts` documents the stability as a guarantee. The `useAutoAdvance` effect and the disconnect effect at `usePlaybackTransport.ts:186-189` also re-run every render, and the latter calls `onDisconnectExtra` on every render while the socket is down.
- **Siblings**: `useStreamStartWatchdog` already stabilises its callback through a ref. The same pattern should apply to `onCleanupExtra` and `onDisconnectExtra`.
- **Related**: #5006 (closed), #4608 (closed, `playEnhanced` stabilisation).
- **Suggested Fix**: Hold `onCleanupExtra` and `onDisconnectExtra` in refs inside the core (or `useCallback` them in `usePlayEnhanced`). Add a render-count or identity test on `controlsValue` across a `currentTime` tick.

### HK-03: A retired WebSocket singleton is never revived, and no remaining UI can call `connect()`
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:197-210`; `auralis-web/frontend/src/utils/errorHandling.ts` (`attemptReconnect`, `POLICY_CLOSE_CODES`); `auralis-web/frontend/src/components/shared/ConnectionStatusIndicator.tsx:74` (the only `connect()` consumer, never mounted)
- **Status**: NEW (related to open #5615)
- **Description**: After `maxReconnectAttempts` failures the manager calls `onMaxAttemptsExceeded`. The hook retires it with `closeCurrentManager()` and sets `connectionStatus='error'`. The attempt count is 10 in production, so the delays 1+2+4+8+16+30+30+30+30+30 s give up after about 3 minutes. In dev the cap is 3, about 7 s. Nothing re-arms the connection afterwards:
  - There is no `online` or `visibilitychange` trigger.
  - There is no timer.
  - `connect()` is only called from `ConnectionStatusIndicator`, which is defined and tested but not mounted anywhere. `grep` finds no `<ConnectionStatusIndicator`.
  - The top bar renders a colour dot only (`AppTopBarStatusIndicator`).
- **Evidence**:
```ts
onMaxAttemptsExceeded: () => {
  if (connState.manager === manager) closeCurrentManager();   // terminal
  if (mountedRef.current) { setIsConnected(false); setConnectionStatus('error'); }
}
```
- **Impact**: If the backend is down for more than about 3 minutes (a slow restart, a crash-restart loop, or a 1008 close), player_state, queue, scan, artwork and playlist live updates and all streaming stay dead until the user reloads the renderer. The only signal is a red dot with no action. `playEnhanced` throws "WebSocket not connected" on every click.
- **Related**: #5615 (open, connection slice write-dead and health poll unmounted), #5602 and #5800 (closed, reconnect policy).
- **Suggested Fix**: Re-arm on `online` and `visibilitychange` events, with a slow periodic probe after retirement. Alternatively mount a reconnect affordance wired to `connect()`.
- **Cross-ref**: A11Y-02 (the mounted status dot has no text or live region either).

### HK-04: `connState.lastStreamCommand` is never cleared by any production path, so reconnect can restart playback unprompted
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:41-45,52-54`; `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:46-67`; `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:186-227` (end/error handlers never touch it)
- **Status**: NEW
- **Description**: `lastStreamCommand` is only nulled when a `stop` or `pause` message passes through `send()` or the queue replay. The frontend never sends either one. Pause is client-only (`pausePlayback` just holds the engine), and `stopPlayback` sends nothing. Searching `type: 'pause'` and `type: 'stop'` finds no sender. The #2385/#3345 invariant "an explicit stop or pause cancels the reconnect resume" is therefore dead code. The command also survives `audio_stream_end`, `audio_stream_error` and watchdog timeouts, which call `cleanupStreaming` and null the engine.
- **Impact**: After a stream error or watchdog timeout the engine is gone (`getPosition()` returns 0). After the queue ends, the last command is still cached. Any later WS reconnect (backend restart, a blip) runs `replayQueueAndResume`, which re-sends `play_enhanced` or `play_normal` from `start_position` (0 after cleanup). The failed or finished track starts playing again with no user action, and `startStreaming` clears the error banner.
- **Siblings**: `reissueActiveStreamAs` also bails out when `lastStreamCommand` is null, so a toggle after the queue ends silently does nothing instead of persisting only.
- **Suggested Fix**: Clear `lastStreamCommand` at the places that actually end a session: `stopPlayback`/`cleanupStreaming`, a completed or errored end with no recovery, and the watchdog. Expose a `clearActiveStream()` on the WS context and call it from there, rather than relying on message types nobody sends.

### TS-01: Settings "Theme" select persists a free `string` that nothing reads; it is disconnected from `ThemeMode`
- **Severity**: MEDIUM
- **Dimension**: Type Safety (root cause) / Component Quality (symptom)
- **Location**: `auralis-web/frontend/src/components/settings/InterfaceSettingsPanel.tsx:40-49`, `auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx:77`, `auralis-web/frontend/src/services/settingsService.ts:34,74`, `auralis-web/frontend/src/contexts/ThemeContext.tsx:32-37`
- **Status**: NEW
- **Description**: `UserSettings.theme` / `SettingsUpdate.theme` are declared `string` (backend `theme: str | None`), while the real theme state is `ThemeMode` (`'light' | 'dark'`) held in `ThemeContext` and persisted only to `localStorage['auralis-theme']`. The Settings dialog Select writes `onSettingChange('theme', e.target.value)` into the backend setting; its displayed value is `getValue('theme') ?? 'dark'`, i.e. the stored DB value, not the live mode. Nothing consumes `settings.theme` (grep: the only reads are `getValue('theme')` and the Select), and `ThemeContext` never calls `settingsService`. The sidebar `ThemeToggle` (`SidebarFooter.tsx:50`) is the only thing that calls `toggleTheme`, and it never writes the setting. Because the field is `string`, the compiler cannot show that the two are unrelated, and `ComfortableApp.tsx:214` reports "Settings saved successfully" regardless.
- **Evidence**:
  ```tsx
  // InterfaceSettingsPanel.tsx
  <Select value={theme} onChange={(e) => onSettingChange('theme', e.target.value)} label="Theme">
    <MenuItem value="dark">Dark</MenuItem><MenuItem value="light">Light</MenuItem>
  // ThemeContext.tsx
  const savedTheme = localStorage.getItem('auralis-theme');  // never reads settings.theme
  ```
- **Impact**: User opens Settings > Interface, picks Light, saves, sees the success toast, and nothing changes. Conversely, after switching with the sidebar toggle, the Settings select still shows the stale DB value. Two controls, two sources of truth, one of them inert.
- **Siblings**: `show_visualizations` (existing #5676) has the same "persisted, never consumed" shape.
- **Related**: #5676, #5646
- **Suggested Fix**: Type `theme` as `ThemeMode` in `UserSettings`/`SettingsUpdate` (and `Literal['light','dark']` server-side), then either drive `ThemeContext` from the persisted setting (apply on load and on save) or delete the Settings control and keep the sidebar toggle as the single control.

### DS-01: MediaCard count/duration badge is unreadable in light mode (dark 80% fill + theme-aware dark ink)
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCardOverlay.tsx:102-117`
- **Status**: Regression of #5641 (issue closed after fixing five surfaces; its unchecked Completeness Check named `MediaCardOverlay.tsx:107-111` as a sibling and it was never migrated)
- **Description**: The badge paints a fixed dark-navy fill (`opacityScale.dark.nearOpaque` = `rgba(11,16,32,0.8)`) but sets `color: themeVars.textPrimary`, which resolves to `#1A1F3A` ink in light mode. This is exactly the "dark fill + theme-aware text" pairing #5641 was opened for; the semantic roles it added (`glassFill`, `glassFillHover`, `menuSurface`, ...) were never applied here.
- **Evidence**:
```tsx
background: tokens.colors.opacityScale.dark.nearOpaque,   // rgba(11,16,32,0.8)
backdropFilter: 'blur(8px)',
color: themeVars.textPrimary,                              // light mode: #1A1F3A
```
  Computed (WCAG): ink `#1A1F3A` on the composited badge fill is 1.56:1 over a white card and 1.13:1 over dark artwork.
- **Impact**: In light mode every album card (`AlbumCard` -> `MediaCard`, `badgeContent = "N tracks"`) and every media card with a duration shows an effectively invisible label. Dark mode (default) is unaffected.
- **Siblings**: `components/track/TrackCardOverlay.tsx` was fixed by #5641 (uses `themeVars.glassFill`), so this is the one surviving instance of the badge pattern.
- **Related**: #5641, #4534, #4877
- **Suggested Fix**: Use `themeVars.glassFill` with a fixed `tokens.colors.text.primaryFull` for the label (the same recipe `TrackCardOverlay` uses for the duration badge), and add a light-mode contrast assertion to `semanticTheme.roles.test.ts`.

### DS-02: Light-mode `surfaceRaised === surfacePrimary` (#FFFFFF); every "raised on primary" affordance collapses
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/semanticTheme.ts:99-101` (root cause); consumers `auralis-web/frontend/src/styles/globalStyles.ts:92-111`, `auralis-web/frontend/src/theme/themeComponents.ts:213-257`, `auralis-web/frontend/src/components/player/VolumeControl.tsx:213`, `auralis-web/frontend/src/design-system/primitives/Slider.tsx:90-158`, `auralis-web/frontend/src/components/library/Styles/Skeleton.styles.ts:27-35`, `auralis-web/frontend/src/components/player/TrackDisplay.tsx:100,163`
- **Status**: NEW
- **Description**: In the light palette both roles map to `tokens.colors.lightMode.background.secondary` (`#FFFFFF`):
  `surfacePrimary: ...background.secondary` (line 99) and `surfaceRaised: ...background.secondary` (line 101). In dark mode `surfaceRaised` (`bg.level3 #1A2338`) is two steps lighter than `surfacePrimary` (`bg.level1`), and about 35 call sites rely on that step to draw tracks, rails, thumbs, skeleton fills and dividers. In light mode the step is zero, and against the canvas (`#F8F9FD`) it is 1.05:1, so those elements disappear. No test pins a minimum distance between the two roles (`semanticTheme.roles.test.ts` covers glass/menu/switch only).
- **Evidence**:
```ts
// semanticTheme.ts light block
surfacePrimary: tokens.colors.lightMode.background.secondary,   // #FFFFFF
surfaceRaised:  tokens.colors.lightMode.background.secondary,   // #FFFFFF  (identical)
// globalStyles.ts:97-110
::-webkit-scrollbar-track { background: surfacePrimary }
::-webkit-scrollbar-thumb { background: surfaceRaised; border: 2px solid surfacePrimary }
scrollbar-color: surfaceRaised surfacePrimary;
// VolumeControl.tsx:213  unfilled part of the volume rail
... ${themeVars.surfaceRaised} ${clampedVolume * 100}%, ${themeVars.surfaceRaised} 100%)
// themeComponents.ts  MuiSlider.rail + MuiSwitch.track (unchecked)
backgroundColor: semantic.surfaceRaised
```
- **Impact**: In light mode the scrollbar thumb is white on white (invisible), the unfilled volume rail and MUI slider rails are 1.05:1 against the canvas (WCAG 1.4.11 needs 3:1), the unchecked MUI Switch track is white on white, and the `SkeletonBox` shimmer (`surfaceSecondary` to `surfaceRaised`, `#FAFBFF` to `#FFFFFF`) and the TrackDisplay buffering skeleton are effectively invisible, so loading states look like blank panels.
- **Siblings**: `design-system/primitives/{Chip,IconButton,Button,Input,Tooltip}.tsx` (`background: themeVars.surfaceRaised` over a primary surface), `components/shared/ui/ThemeToggle.styles.ts:30`, `components/shared/KeyboardShortcutsHelp.styles.ts:6,18` (divider drawn in `surfaceRaised` on a `surfaceRaised` panel), `components/player/BufferingIndicator.tsx:136`, `components/player/QueuePanel/styles.ts:190` (dragging row).
- **Related**: #5675 (open, WCAG contrast of accent/status text in light mode - different roles), #5641
- **Suggested Fix**: Give the light palette a distinct raised step (for example `lightMode.background.hover` `#F0F2F8`, or a new `lightMode.background.raised`) and add a role test asserting `contrast(surfaceRaised, surfacePrimary/canvas)` meets at least 3:1 for rails/thumbs, or introduce dedicated `rail`/`track` roles for the rail/scrollbar/skeleton cases.

### DS-03: Inline `@keyframes pulse/spin/fadeIn` are global by name; four different `pulse` definitions fight (last-injected wins)
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/shared/DropZone/DropZoneStyles.ts:62-90`, `auralis-web/frontend/src/components/settings/SettingsTabNav.tsx:38-42`, `auralis-web/frontend/src/components/shared/feedback/ProcessingToast.tsx:80-85`, `auralis-web/frontend/src/styles/globalKeyframes.ts:8-14` (global definition); bare-name consumers `auralis-web/frontend/src/components/player/TrackDisplay.tsx:102`, `auralis-web/frontend/src/components/shared/ConnectionDetailsPanel.tsx:68`
- **Status**: NEW (the closed #4188 centralised the *injected `<style>`* cases; the sx-nested `@keyframes` cases were not addressed, and the #5841 split kept the global names)
- **Description**: Emotion does not scope `@keyframes` declared inside an object style: serialising `{animation:'pulse 2s', '@keyframes pulse': {...}}` through `@emotion/serialize` + `stylis@4.2.0` (the versions in `node_modules`) yields `.css-x{animation:pulse 2s;}@keyframes pulse{0%,100%{opacity:0.05;}50%{opacity:0.1;}}` - an unprefixed global `@keyframes pulse`. The app therefore has four same-named `pulse` keyframes with different bodies: global `1 -> 0.6` (`globalKeyframes.ts`), DropZone `0.05 <-> 0.1`, ProcessingToast `1 <-> 0.5`, SettingsTabNav `1 <-> 0.3`. Consumers that rely on the name without defining it (`TrackDisplay` skeleton `pulse 2s`, `ConnectionDetailsPanel` reconnect dot `pulse 1s`) get whichever definition was inserted last. `spin` (4 copies: global, `Spinner.styles`, `ArtistListLoadingIndicator`, and bare users `BufferingIndicator:188`, `SearchBar:222`) and `fadeIn` (global opacity-only vs DropZone scale+opacity) have the same shape, though the spin copies happen to be identical.
- **Evidence**:
```ts
// DropZoneStyles.ts:62-65 (inside a styled() style function)
'@keyframes pulse': { '0%, 100%': { opacity: 0.05 }, '50%': { opacity: 0.1 } },
// TrackDisplay.tsx:102 -- no local definition
animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
```
- **Impact**: Once the empty-library `DropZone` (rendered by `EmptyState`) has mounted in a session, its rule is injected after the global one and wins for every bare-`pulse` consumer: the buffering skeleton in `TrackDisplay` and the reconnecting dot in `ConnectionDetailsPanel` then animate between 5% and 10% opacity (near-invisible) for the rest of the session. Behaviour depends on mount order, so it is intermittent and hard to diagnose.
- **Siblings**: `TrackCardStyles.ts:23` (`shimmer` translateX vs global `shimmer` background-position, currently harmless because the global user `.skeleton` is dead - see DS-11), `DropZoneStyles.ts:81` (`fadeIn`), `Spinner.styles.ts:23` and `ArtistListLoadingIndicator.tsx:38` (`spin`).
- **Related**: #4188 (closed, related mechanism), #5648
- **Suggested Fix**: Define each animation once - either the global names in `globalKeyframes.ts` only (delete the nested copies) or Emotion's `keyframes` helper for hashed names (as `Skeleton.styles`, `LoadingSpinner`, `ProgressiveImage` already do) - and give DropZone's variant a unique name such as `dropzone-pulse`.

### API-01: React Query caches (album grid, album/track fingerprints) are never invalidated, so they go stale after a scan, auto-scan or metadata edit
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:78-97`; `auralis-web/frontend/src/App.tsx:18-27`; `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:88-100, 146-156`; `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:76-84`
- **Status**: NEW
- **Description**: The Albums view (`CozyAlbumGrid` -> `useInfiniteAlbums`) is the only production consumer that moved to React Query, with the app-wide `staleTime: QUERY_STALE_TIME_MS` (5 min) and no `refetchOnMount`/`refetchOnWindowFocus` override (`refetchOnWindowFocus: false`). Nothing in `src/` ever calls `invalidateQueries`/`refetchQueries`/`setQueryData` for `['albums', ...]` or `['album-fingerprint'|'track-fingerprint', ...]` (the only `invalidateQueries` call is for the `['cache']` telemetry key in `useStandardizedAPI.ts:87`). The library-change signal that every other list uses, the `library_updated` WebSocket broadcast, is subscribed only in `useLibraryWithStats`, which refreshes the track list (`useLibraryPagination`) and stats, not the React Query caches. So when the backend scans (Settings "Scan Now", the auto-scanner, `missing_tracks` pruning) or a metadata edit changes album titles/years, the album grid keeps serving the cached pages until the 5-minute stale window lapses AND the grid remounts. The same applies to `useAlbumFingerprints`: a `404 -> null` (fingerprint not ready yet) is a *successful* query result cached for 5 min, and the album hook does not poll (unlike `useTrackFingerprint`), so tile colouring stays on the hash-gradient fallback after the backend finishes fingerprinting. (Library reset is fine: `AdvancedSettingsPanel.tsx:107` reloads the window.)
- **Evidence**:
  ```ts
  // App.tsx: queries: { staleTime: QUERY_STALE_TIME_MS, refetchOnWindowFocus: false, retry: shouldRetryQuery }
  // useInfiniteAlbums.ts: queryKey: ['albums', { search, limit }]   // no library-revision component in the key
  // grep -rn "invalidateQueries|refetchQueries|resetQueries" src  -> only hooks/shared/useStandardizedAPI.ts (['cache'])
  // useLibraryWithStats.ts: useWebSocketMessages(['library_updated'], handleLibraryUpdated) // refreshTracks() + refetchStats() only
  ```
- **Impact**: Add a folder, finish a scan, open Albums within 5 minutes of the last visit: new albums are missing; renamed albums keep their old title; clicking an album that the scan removed gives "Album not found". Workaround: wait 5 min / restart.
- **Siblings**: `useAlbumFingerprints`/`useAlbumFingerprint`/`useTrackFingerprint` (fingerprint caches, `gcTime` 30 min); `CozyArtistList` is not affected (custom hook, refetches on every mount).
- **Related**: #5650 (queryFn cancellation, same hooks, different defect).
- **Suggested Fix**: Subscribe once at the QueryClientProvider level to `library_updated` (and the fingerprint-complete event) and call `queryClient.invalidateQueries({ queryKey: ['albums'] })` / `['album-fingerprint']`; or fold a library revision counter into the keys.

### PERF-02: refreshTracks re-fetches every loaded page sequentially, and every library_updated / edit / batch op triggers it
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:148-190`; callers `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:79-84`, `components/library/CozyLibraryView.tsx` (`useMetadataEditing(refreshTracks)`, `useBatchOperations({ onFetchTracks: refreshTracks })`)
- **Status**: NEW (#5626 introduced the in-place refresh; its cost scaling was not addressed)
- **Description**: `refreshTracks` loops `while (refreshed.length < loaded && more)` and awaits one `GET /api/library/tracks?limit=50&offset=N` per iteration. The state is committed only after the last page. A user who has scrolled N tracks deep pays N/50 serial round trips on every `library_updated` broadcast (scan completion, auto-scan, folder removal), every metadata save and every bulk action. A second trigger arriving mid-loop aborts the in-flight request and restarts from offset 0. `fetchInProgressRef` stays true for the whole loop, so `loadMore` is a no-op during it. When it finishes, `setTracks(refreshed)` swaps every object identity (10k+ `LibraryTrack` instances), so all mounted rows re-render.
- **Evidence**:
  ```ts
  while (refreshed.length < loaded && more) {
    fetchAbortRef.current?.abort();
    controller = new AbortController(); ...
    const page = await fetchTracksPage(view, newOffset, controller.signal);
    refreshed.push(...page.tracks); newOffset += PAGE_LIMIT;
  }
  setTracks(refreshed);
  ```
  `PAGE_LIMIT = 50` (`libraryPageFetch.ts:15`). 10,000 loaded tracks means 200 sequential requests.
- **Impact**: On large libraries, a metadata edit or a background auto-scan broadcast causes a long burst of backend queries (each a SQLite page read). The list stays on stale data until the loop ends, scrolling cannot load more meanwhile, and a late refresh finishes with a whole-list re-render.
- **Siblings**: `useLibraryQuery.refetch` resets to page 0 only (not affected).
- **Related**: #5626 (closed), #4891.
- **Suggested Fix**: Refresh with a single larger request (e.g. `limit=loaded`, capped), or refresh only the pages intersecting the viewport and invalidate the rest. At minimum, patch rows by id for single-track edits instead of reloading, and coalesce overlapping triggers.

### PERF-03: Artist detail Tracks tab renders every track unvirtualized and passes `isPlaying` to every row
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Views/TracksTab.tsx:52-63`; `auralis-web/frontend/src/components/library/Views/ArtistTrackRow.tsx:16-24,38-51`
- **Status**: NEW (sibling gap of #3576/#3928/#5660; #4472 only added `memo`)
- **Description**: The main library list (TrackListViewContent / TrackGridView) is virtualized and avoids per-row `isPlaying` via a container attribute (#5660). `TracksTab` still does `tracks.map` into MUI `<Table>` rows for the whole artist (`DetailTrack[]`, no pagination), and passes the global `isPlaying` boolean to every `ArtistTrackRow`. The row only reads `isPlaying` when `isCurrentTrack` is true, but the prop differs for all rows on each play/pause, so `memo` is defeated for the whole list.
- **Evidence**:
  ```tsx
  {tracks.map((track, index) => (
    <ArtistTrackRow ... isCurrentTrack={currentTrackId === track.id}
                    isPlaying={isPlaying} ... />
  ))}
  ```
  Each row mounts a `StyledTableRow`, 3 `TableCell`s, 3 `Typography`, an icon pair and `sx` objects.
- **Impact**: For an artist with several hundred or thousands of tracks (compilations, "Various Artists"), opening the tab mounts that many MUI rows at once. Every play/pause toggle (including via keyboard shortcuts) re-renders all of them.
- **Siblings**: `components/library/Views/AlbumsTab.tsx:87` maps all of an artist's albums unvirtualized, but album counts are small. `SimilarTracksModal.tsx:175` is bounded server-side.
- **Related**: #3576, #3928, #5660, #4472 (all closed).
- **Suggested Fix**: Pass `isPlaying={isCurrentTrack && isPlaying}` so only one row changes. Virtualize with the existing `useVirtualizer` + `#app-main-content-scroll` pattern already used in TrackListViewContent.

### A11Y-01: Track context-menu events bubble through the React tree into the listbox keydown handler and the row-container click handler
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:147-172,193-200`; `auralis-web/frontend/src/components/library/Items/tracks/SelectableTrackRow.tsx:78-80`; `auralis-web/frontend/src/components/library/Items/tracks/useTrackRowSelection.ts:15-22`; `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:182`
- **Status**: NEW
- **Description**: `TrackRow` renders `<ContextMenu>` (a MUI `Menu`, portalled to `document.body`) as a sibling of `RowContainer`, inside `SelectableContainer` inside the `role="listbox"` div. React synthetic events bubble along the React tree, not the DOM tree, so every keydown and click inside the open menu (and its backdrop) also reaches (a) `handleListboxKeyDown` and (b) `SelectableContainer`'s `handleContainerClick`. Neither handler checks that the event originated in its own DOM subtree. MUI's `MenuList` handles ArrowUp/Down/Home/End with `preventDefault()` only (MUI 9.0.1 `MenuList.js:231`; `Modal/useModal.js:120` stops propagation for Escape only).
  - Keyboard: ArrowDown/ArrowUp/Home/End in the menu is also read by `handleListboxKeyDown`, which calls `e.preventDefault()`, `virtualizer.scrollToIndex(next)`, `setActiveIndex(next)` and sets `shouldFocusRef`, so the focus effect (`:121-140`) calls `row.focus()` on the neighbouring track row. Focus is pulled out of the menu while it is open; MUI's focus trap then drags it back to the menu root rather than to the item the user was moving to (the trap's re-focus behaviour is inferred from MUI's `contain()`; the bubbling itself is confirmed).
  - Pointer: `handleContainerClick` only skips targets inside a `button`/`[role=button]`. A menu item is an `li[role=menuitem]` and the backdrop is a `div`, so clicking any context-menu action, or clicking outside to dismiss the menu, calls `onToggleSelect` and toggles that row's batch selection (the batch toolbar appears/disappears as a side effect).
- **Evidence**:
  ```tsx
  // TrackListViewContent.tsx:154-170  no check of e.target / defaultPrevented
  case 'ArrowDown': next = Math.min(activeIndex + 1, tracks.length - 1); break;
  ...
  e.preventDefault(); ... shouldFocusRef.current = true; setActiveIndex(next);
  // useTrackRowSelection.ts:16-21
  const isActionButton = target.closest('button') || target.closest('[role="button"]');
  if (!isActionButton) onToggleSelect(event);
  ```
- **Impact**: Keyboard and screen-reader users of the library track list cannot reliably navigate the context menu with arrow keys (the primary route to "Add to playlist", "Edit metadata", "Find similar"). Every mouse use of the menu also silently flips selection state.
- **Siblings**: `TrackTableRowItem.tsx:131` mounts the same `ContextMenu` but its ancestors have no key/click handlers, so it is not affected today. Any future ancestor handler would inherit the problem.
- **Related**: #5658 (closed, nested-button keydown on rows) was fixed on the DOM side only. #5617 and #5614 (open) are about menu contents, not events.
- **Suggested Fix**: In `handleListboxKeyDown` and `handleContainerClick`, return early unless `e.currentTarget.contains(e.target as Node)` (DOM containment), or stop propagation in `ContextMenu` on the `Menu` root (`onKeyDown`/`onClick` stopPropagation).

### A11Y-02: Connection state reaches the user only as a 12px colour dot; the accessible indicator is orphaned
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/core/AppTopBar.tsx:148`; `auralis-web/frontend/src/components/core/AppTopBarStatusIndicator.tsx:13-17`; `auralis-web/frontend/src/components/core/AppTopBar.styles.ts:48-55`; `auralis-web/frontend/src/components/core/useConnectionStatus.ts:15-27`; `auralis-web/frontend/src/components/shared/ConnectionStatusIndicator.tsx` (no importer outside tests)
- **Status**: NEW
- **Description**: The only connection-status surface mounted in the app is `AppTopBarStatusIndicator`, a styled `Box` with a background colour: no text, no `role`, no `aria-label`, no live region. Green/amber/red is the sole channel (WCAG 1.4.1, 4.1.3). `connecting`, `disconnected` and the permanent `error` state map to nearly the same visual treatment and none is announced. The fully accessible `ConnectionStatusIndicator` (text "Connected / Reconnecting... / Disconnected", `aria-label`, details panel with Reconnect button) is imported only by `Integration.test.tsx` and its own spec, so the tests keep passing while the shipped app has none of that behaviour. (If that component were mounted it would also be wrong: `<button role="status" aria-live="assertive">` replaces the button role.)
- **Evidence**:
  ```tsx
  // AppTopBar.tsx:148
  <AppTopBarStatusIndicator color={statusColor} />
  // AppTopBarStatusIndicator.tsx:17
  return <StatusIndicator color={color} />;   // <div style="background: <color>">
  ```
  `grep -rn ConnectionStatusIndicator src | grep -v test` returns only the file itself and doc comments.
- **Impact**: A screen-reader user is never told the WebSocket dropped, is reconnecting, or gave up (playback silently stops responding); colour-blind users distinguish green from red by hue alone.
- **Siblings**: `SettingsTabNav.tsx:34-46` shows a pulsing green dot on the Library tab while scanning with no text alternative (the same colour/animation-only pattern; low impact because `ScanStatusCard` has text).
- **Related**: closed #3270, #3003, #3165 fixed `ConnectionStatusIndicator` itself; that fix no longer reaches any user.
- **Suggested Fix**: Give the top-bar indicator `role="status"` with a visually hidden text label ("Connected" / "Reconnecting" / "Disconnected", polite live region, no announcement on first mount), or mount the existing `ConnectionStatusIndicator` and delete the dot.
- **Cross-ref**: HK-03 (the connection gives up permanently after the reconnect budget, and the only `connect()` caller is this unmounted component).

### A11Y-03: Opening or leaving an album/artist detail view neither moves focus nor announces the change
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/useNavigationState.ts:11-32`; `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:172-184`; `auralis-web/frontend/src/ComfortableApp.tsx:49,137`; `auralis-web/frontend/src/components/core/AppViewAnnouncement.tsx:24-37`; `auralis-web/frontend/src/components/library/Details/DetailViewHeader.tsx:134-139`
- **Status**: NEW
- **Description**: Detail navigation (album card click, artist click, Back) lives in `useNavigationState` inside `CozyLibraryView`; `ComfortableApp.currentView` does not change, so `AppViewAnnouncement` (the only view-change announcer, keyed on `view`) stays silent. There is also no focus management on these transitions: `grep -rn "\.focus(\|tabIndex={-1}"` finds no focus move to the new `<h1>` anywhere outside dialogs, list navigation and the search shortcut. The activated card/row is unmounted when the grid is replaced by `AlbumDetailView`/`ArtistDetailView`, so focus falls to `<body>`; on Back the grid is rebuilt from scratch with focus again on `<body>` and no restored position.
- **Evidence**:
  ```tsx
  // CozyLibraryView.tsx:172
  if (view === 'albums' || view === 'artists' || selectedAlbumId !== null || selectedArtistId !== null) {
    return <LibraryViewRouter ... />   // replaces the grid; no focus handoff
  // AppViewAnnouncement is rendered once with view={currentView} (ComfortableApp.tsx:137)
  ```
- **Impact**: A keyboard user presses Enter on an album and ends on `<body>` with the page silently replaced; a screen-reader user hears nothing. Back repeats it. This is the main drill-down path of the Albums and Artists views.
- **Related**: closed #4961 (sidebar view switch announced) and #5391 (detail views have an h1) did not cover in-view navigation; #5671 (open) is about heading levels only.
- **Suggested Fix**: On detail enter/leave, focus the new view's `<h1>` (`tabIndex={-1}` + `ref.focus()` in an effect) and, on Back, refocus the card that opened it; or extend the announcement to include the detail title ("Album: X").

### A11Y-04: Queue rows are one tab stop each with no arrow-key navigation, and the code comment claiming otherwise is wrong
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueueTrackItem.tsx:52-100` (comment at `:78-82`); `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:206-250`
- **Status**: NEW
- **Description**: Each queue `<li>` has `tabIndex={0}`. There is no roving tabindex and no ArrowUp/ArrowDown handler: the only key handlers are Delete/Backspace and Alt+Arrow (reorder). The comment justifying Alt+Arrow says plain arrows "the browser uses to move between rows"; browsers do not move focus between `li[tabindex=0]` elements on arrow keys, and no handler on the `ul`/container does. A user who follows the `aria-keyshortcuts` hint finds plain arrows do nothing. A queue of N tracks is N tab stops (virtualized with overscan 5, so rows mount progressively as focus scrolls), and the Remove button appears only after a row is focused, adding another stop. This is the exact defect fixed for the library list in #5011 (roving tabindex, APG pattern), left undone for the queue.
- **Evidence**:
  ```tsx
  // QueueTrackItem.tsx:57-58,78-82
  role="listitem" tabIndex={0} ...
  // Alt-modified arrows reorder (#4536). Alt keeps this off plain
  // ArrowUp/ArrowDown, which the browser uses to move between rows
  ```
- **Impact**: Queue management by keyboard (play-all-album queues easily reach hundreds of tracks) needs hundreds of Tab presses to reach a track near the end; Shift+Tab is the only way back to the queue controls above the list.
- **Related**: #5672 (open) covers list size/position exposure for the same list; this is operability. Closed #5011, #4536.
- **Suggested Fix**: Reuse the roving-tabindex + ArrowUp/Down/Home/End pattern from `TrackListViewContent` (one `tabIndex=0` row, `virtualizer.scrollToIndex` on move), and correct the comment.

### A11Y-05: Removing a queue row by keyboard strands focus on `<body>` and is not announced
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueueTrackItem.tsx:73-77,108-122`; `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:112-118`; contrast with `auralis-web/frontend/src/components/player/QueuePanel/useQueueKeyboardReorder.ts:36-112`
- **Status**: NEW
- **Description**: Delete/Backspace on a focused row calls `onRemove(index)` immediately: no confirmation, no live-region message, no focus handoff. The row (and its Remove button, if that was focused) unmounts, so focus is lost. Reordering got the full treatment in #4536 (restored focus + "X moved to position N of M" status region); removal, the other destructive keyboard action on the same rows, was not given either. Backspace is also a plausible accidental key.
- **Evidence**:
  ```tsx
  if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault();
    if (!disabled) onRemove(index);   // nothing focuses a neighbour or announces
    return;
  }
  ```
- **Impact**: Screen-reader users get no confirmation a track was removed; keyboard users lose their place in the queue after every removal and must Tab in from the document start.
- **Suggested Fix**: After removal, focus the row now at the same index (or the previous one) via the same layout-effect mechanism `useQueueKeyboardReorder` uses, and add "X removed from queue" to the existing `role="status"` region.

### A11Y-06: VolumeControl focus indicator is a 30%-alpha accent ring at about 1.4:1 contrast
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/VolumeControl.tsx:145-151,209-212`; `auralis-web/frontend/src/theme/semanticTheme.ts:84,127`
- **Status**: NEW
- **Description**: The mute button and the volume range input set `outline: none` and draw their keyboard focus ring with `themeVars.focusRing`, which both themes resolve to `opacityScale.accent.strong` = `rgba(115,102,240,0.30)`. Composited over the canvas/surface that ring is about 1.43:1 against its background (dark `#0B1020`: 1.43, `#101729`: 1.45, `#1A2338`: 1.44; light `#F8F9FD`: 1.45), far under the 3:1 required for focus indicators (WCAG 1.4.11, and 2.4.11 in WCAG 2.2). Inline `outline` also overrides the global `:focus-visible` rule (`styles/globalStyles.ts:124`, solid accent, 4.15:1), so these are the two always-visible controls in the player whose focus is effectively invisible. The sibling controls use the solid accent (`PlaybackControls.tsx`, `Player.styles.ts:95`).
- **Evidence**:
  ```tsx
  // VolumeControl.tsx:147-150
  outline: 'none',
  ...(isMuteButtonFocused && !disabled && { outline: `3px solid ${themeVars.focusRing}`, ... })
  // semanticTheme.ts:84  focusRing: tokens.colors.opacityScale.accent.strong   // rgba(115,102,240,.30)
  ```
- **Impact**: Keyboard users tabbing across the player cannot see when the mute button or the volume slider has focus (the mute button also gets only a `surfaceSecondary` background change).
- **Siblings**: `AppTopBar.styles.ts:41` and `theme/themeComponents.ts:144` use `focusRing` as a 3px box-shadow halo, but both also change the border to solid accent, so they pass. `focusRing` is also used as `::selection` background (`globalStyles.ts:119`).
- **Suggested Fix**: Use `themeVars.accent` (or `accentHover` in dark) for the outline colour, matching the other player controls, and reserve `focusRing` for halos.

### A11Y-07: SegmentedControl removes the outline and defines no focus style
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/design-system/primitives/SegmentedControl.tsx:84-90,113-131`; consumer `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:164`
- **Status**: NEW (unswept sibling of closed #2801, "outline: none on buttons without :focus-visible replacement")
- **Description**: `SegmentButton` sets `outline: 'none'` under "Reset" and has hover and active rules but no `:focus-visible` rule. Emotion class and the global `:focus-visible` rule have equal specificity, and the component rule is inserted later, so the global ring does not apply (inferred from emotion's insertion order; the missing replacement is confirmed). The selected state is a barely visible `white.subtle` (8%) fill. The rest of the codebase's #2801 fix (`PlaybackControlsStyles`, `Player.styles`, `AlbumActionButtons`, `ArtistHeader`) adds an explicit `&:focus-visible`.
- **Evidence**:
  ```ts
  // SegmentedControl.tsx:86-88
  // Reset
  border: 'none',
  outline: 'none',
  ```
- **Impact**: The Albums-view sort control ("A-Z", etc.) is keyboard-operable but shows no focus position (WCAG 2.4.7).
- **Suggested Fix**: Add `'&:focus-visible': { outline: \`2px solid ${themeVars.accent}\`, outlineOffset: '2px' }` to `SegmentButton`.

### A11Y-08: Non-current library rows are dimmed with element `opacity: 0.6` while anything plays, dropping text below AA
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts:19-25,199-206,230-245`; `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:199`
- **Status**: NEW
- **Description**: `data-any-playing="true"` on the listbox (set whenever a track is playing, i.e. the app's normal state) applies `opacity: 0.6` to every non-current `RowContainer`. Element opacity composites the text with the surface, so the text tokens no longer have the contrast the token files claim (the #2803 comment "metadata >= 60% for 4.5:1"). Computed against the list Paper (`white 5%` over the canvas), dark mode: artist/secondary text (`rgba(255,255,255,.68)`) 8.4:1 falls to 3.88:1; metadata/duration (`.60`) 6.83:1 falls to 3.32:1; title (`.95`) falls from 15.4 to 6.3 (still passes). Light mode: secondary text `#5A6280` 5.71:1 falls to 2.52:1 and the primary title `#1A1F3A` to 4.26:1. The dimming is a deliberate "playback dominance" design choice, but there is no exemption in WCAG 1.4.3 for de-emphasised-but-interactive content, and hover restores full opacity only for mouse users (keyboard focus does not).
- **Evidence**:
  ```ts
  '[data-any-playing="true"] &': { opacity: iscurrent === 'false' ? 0.6 : 1 },
  ```
- **Impact**: While music plays, the artist, album and duration columns of every other row are low-contrast; light-theme users lose most of the secondary text.
- **Siblings**: `MediaCard` / `TrackTableRowItem` do not dim; only `TrackRow` does.
- **Related**: #5675 (open) covers light-mode accent/status colours, not element opacity. Closed #2803/#4182 fixed the base token contrast that this rule then undoes.
- **Suggested Fix**: Dim by lowering contrast on non-text parts only (artwork, row background) or add `&:focus-visible, &:focus-within { opacity: 1 }` and pick a dimming level that keeps secondary text at 4.5:1 (about 0.85 in dark mode).

### TEST-02: usePlaybackQueue.test.ts — 28 of its specs now fail, 21 of them unbaselined, because #5601 added a `player` selector the spec's store lacks
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/player/__tests__/usePlaybackQueue.test.ts:21` (`configureStore({ reducer: { queue: queueReducer } })`); `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:47`
- **Status**: NEW
- **Description**: 365c8f67 (#5601, 2026-10-19) made `useQueueSubscription` call `useSelector(playerSelectors.selectCurrentTrack)`. `usePlaybackQueue` composes that hook, so every `renderHook(() => usePlaybackQueue())` in this spec now throws `TypeError: Cannot read properties of undefined (reading 'currentTrack')` at `store/selectors/player.ts:20`, because the spec's private store only has the `queue` slice. Reproduced locally (28 failures in the file, independent of jsdom version); only 7 of those titles are in `test-baseline.json`, so 21 are new failures in CI. The 7 baselined entries were already failing before #5601, so the file had already lost coverage before this regression.
- **Evidence**:
  ```ts
  // usePlaybackQueue.test.ts:21
  const createTestStore = () => configureStore({ reducer: { queue: queueReducer } });
  // useQueueSubscription.ts:47
  const playingTrackId = useSelector(playerSelectors.selectCurrentTrack)?.id;   // state.player is undefined
  ```
- **Impact**: The facade spec for queue state (setQueue/add/remove/reorder/shuffle/repeat, rollback on API failure, callback stability) is effectively dead. The production store has the player slice, so runtime behaviour is unaffected, but queue-mutation regressions through `usePlaybackQueue` have no covering spec. The #5601 change shipped without anyone running this file.
- **Siblings**: seven other specs build a queue-only store (`useQueueFetch.test.ts:21`, `useQueueMutations.{optimistic,reorder,shuffle,sameTick,staleRollback}.test.ts`, `deterministic-timestamps.test.ts:20`). They do not render `useQueueSubscription`, so they pass today, but they have the same latent trap. The shared `createTestStore()` in `test/test-utils.tsx` already includes the player slice.
- **Related**: TEST-01, #5681 (each spec hand-rolls a store).
- **Suggested Fix**: Use `createTestStore()` from `@/test/test-utils` (or add `player: playerReducer`) in this spec, then drop its 7 baseline entries if they pass.


## Low (51)

### CMP-11: `EmptyLibrary` creates a new `lazy()` component on every render
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/ui/feedback/EmptyState.tsx:73`
- **Status**: NEW
- **Description**: `const DropZone = lazy(...)` is declared inside the `EmptyLibrary` function body. Every render of `EmptyLibrary` yields a new component type, so React unmounts the previous `DropZone` (losing its drag state) and re-suspends, flashing the `<div>Loading...</div>` fallback. `EmptyLibrary` is not memoised and re-renders whenever `LibraryEmptyContent`'s props change (e.g. `scanning` flipping during a scan) or the parent re-renders.
- **Evidence**:
  ```tsx
  export const EmptyLibrary = (...) => {
    const DropZone = lazy(() => import('@/components/shared/DropZone/DropZone').then(...));
  ```
- **Impact**: A flash of "Loading..." and a DropZone remount whenever the empty-library screen re-renders (scan start/finish); drag-over highlight is lost mid-drag.
- **Siblings**: none (other `lazy()` calls are module-level).
- **Suggested Fix**: Hoist the `lazy()` call to module scope (or import DropZone statically - it is tiny).
- **Merged**: Also found by the Performance dimension (PERF-06).

### CMP-12: Artist detail error/not-found state has no way back, unlike its sibling Album detail
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Details/ArtistDetailView.tsx:73-91` vs `auralis-web/frontend/src/components/library/Details/AlbumDetailView.tsx:105-140`
- **Status**: NEW
- **Description**: The comment in `ArtistDetailView` says it applies "the identical fix" as `AlbumDetailView`, but only the title logic was copied. `AlbumDetailView`'s error branch renders a "Back" button wired to `onBack`; `ArtistDetailView`'s error branch renders only the `EmptyState` (the back arrow lives in `ArtistDetailHeaderSection`, which is not rendered in that branch). The `artistName` prop is also accepted and never used (it could have labelled the error).
- **Evidence**:
  ```tsx
  // ArtistDetailView.tsx:85  <EmptyState title={notFound ? 'Artist not found' : 'Error Loading Artist'} .../>   // no onBack control
  ```
- **Impact**: After a 404/500 on an artist, the user's only exits are the sidebar items (and CMP-10 makes same-view sidebar clicks a no-op).
- **Siblings**: CMP-07 (error states without a retry action).
- **Suggested Fix**: Add the same Back button (and a Retry) to the error branch; share a small `DetailError` component between the two views.

### CMP-13: Region error boundaries have no reset trigger for state-driven crashes, and the Settings/Shortcuts fallbacks cannot close their dialogs
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:198-257`, `auralis-web/frontend/src/components/player/Player.tsx:204-216`, `auralis-web/frontend/src/components/core/ErrorBoundary.tsx:59-72`, `auralis-web/frontend/src/ComfortableApp.tsx:10-12`
- **Status**: NEW (the "retry unreachable" defect of #5627 itself is fixed; this is what remains)
- **Description**: All four region boundaries now use `RegionErrorFallback` with a working retry, and the library boundary has `resetKeys=[currentView]`. The others have none. (1) Settings and Shortcuts dialogs: the parent keeps `settingsOpen`/`isHelpOpen` true, so after a render crash the retry remounts a still-`open` dialog and, for a deterministic throw, crashes again; the fallback is rendered inline in the root flex column (not in a dialog), with no way to set the open flag back to false. (2) Player and its inner QueuePanel boundary are driven by Redux state (current track / queue), so the same bad data re-crashes on every retry; `resetKeys` on e.g. `currentTrack?.id` / queue length would let the next track recover without a click. (3) All three route-level components are `React.lazy`; a rejected dynamic import is cached by React, so the boundary's retry re-throws the same rejection (no way to recover from a chunk-load failure short of reload). `onError` is wired nowhere, so boundary catches only reach `console.error`.
- **Evidence**:
  ```tsx
  <ErrorBoundary fallback={(_e, retry) => (<RegionErrorFallback message="Settings failed to render..." retry={retry} />)}>
    <Suspense fallback={null}><SettingsDialog open={settingsOpen} .../></Suspense>
  ```
- **Impact**: A sticky red box between the library and the player for the remainder of the session after one Settings/Shortcuts render error; Player/queue recovery needs a manual click that usually re-fails.
- **Siblings**: Root boundary in `index.tsx` (default fallback, retry works; fine).
- **Suggested Fix**: Add `resetKeys={[settingsOpen]}`/`[isHelpOpen]` plus a "Close" action that clears the flag; add `resetKeys` for Player/Queue; wrap lazy imports with a retry-on-reject factory.

### CMP-14: StarfieldBackground leaks a GL buffer and two shaders on every re-init and has no context-loss handling
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/background/StarfieldBackground.tsx:92-148,203-276`
- **Status**: NEW
- **Description**: The main effect depends on `audioIsActive`, `prefersReducedMotion`, `mode`, `draw` and `handleMouseMove`, and calls `initWebGL()` on each run. `initWebGL` compiles two new shaders (never `deleteShader`'d after linking) and `gl.createBuffer()` (never deleted); cleanup only `deleteProgram`s. Every play/pause toggle re-runs the effect on the same context, leaking a buffer and two shader objects each time. There is no `webglcontextlost`/`restored` listener, so a lost context leaves a frozen/black canvas until the theme changes. While idle (audio stopped, settled) there is no resize handling, so a window resize stretches the last frame.
- **Evidence**:
  ```ts
  const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); ...   // never deleteBuffer
  // cleanup: gl.deleteProgram(programRef.current)   // shaders + buffer left
  ```
- **Impact**: Slow GPU object growth over a long session (small objects, but unbounded in count); black background after a GPU reset.
- **Siblings**: none.
- **Suggested Fix**: Create GL resources once per context (not per effect run) or delete shaders after link and the buffer in cleanup; add context-lost/restored listeners; redraw on resize while idle.
- **Merged**: Also found by the Performance dimension (PERF-05), which adds: the effect lists `audioIsActive` in its deps to restart the rAF loop, so every play/pause recompiles and relinks the heavy fragment shader on the main thread (cost not measured).

### CMP-15: `AudioPlaybackEngine.ts` is 308 lines
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts` (308 lines)
- **Status**: NEW
- **Description**: Re-measured with `wc -l` over shipped (non-test) `src/` files: the only file over 300 lines is this service. The next largest are `useLibraryQuery.ts` 298, `starfield.shaders.ts` 296, `StarfieldBackground.tsx` 296 and `AlbumCharacterPane.tsx` 295 - each within 5 lines of the limit. No `.tsx` component exceeds 300 (largest 296).
- **Evidence**: `wc -l` output above.
- **Impact**: Style-guide only (not a component).
- **Siblings**: files at 290-298 lines will cross the limit with the next feature.
- **Suggested Fix**: Extract the remaining ~10 lines (e.g. a constants or lifecycle helper) as was done for the other split modules.

### RDX-06: `player_state` seq watermark is reset in an effect, so the first snapshot after a backend restart can be dropped as "stale"
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:82-93,103-108`
- **Status**: NEW (fix for closed #4338 is order-sensitive)
- **Description**: #4338 resets `lastSeenSeqRef` in a `useEffect` keyed on `connectionStatus === 'connected'`. The backend pushes the full snapshot immediately on connect (`ws_handlers/connection.py:150-160`) and `useWebSocketConnection` sets the status from `onopen` as React state, so the snapshot message can be handled before the effect runs. After a backend restart the new process's seq restarts near 0, so `state.seq < lastSeenSeqRef.current` discards that one snapshot and nothing re-sends it (later snapshots only follow mutations).
- **Evidence**:
  ```ts
  useEffect(() => { if (connectionStatus === 'connected') { lastSeenSeqRef.current = 0; ... } }, [connectionStatus]);
  ...
  if (state.seq < lastSeenSeqRef.current) return;      // runs from the WS onmessage, not from React
  ```
- **Impact**: Timing-dependent (not confirmed at runtime) and rare (backend respawn without a frontend reload): Redux keeps the pre-restart queue/track while `useServerRestartNotice` tells the user the session was reset.
- **Siblings**: the three other watermarks reset in the same effect (`lastSeenTrackChangedSeqRef`, `lastSeenTransportEventSeqRef`, `lastSeenVolumeEventSeqRef`).
- **Related**: #4338, #5487.
- **Suggested Fix**: Reset on `server_instance_id` change (already on every snapshot) or reset synchronously from the connection-open callback instead of a post-render effect.

### RDX-07: `addTrack` at a position into an empty queue pushes `currentIndex` out of range
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:41-52`
- **Status**: NEW
- **Description**: The #4927 shift (`if (pos <= state.currentIndex) state.currentIndex += 1`) ignores the empty-queue case. With `tracks = []`, `currentIndex = 0`, `addTrack(t, 0)` inserts the only track and sets `currentIndex = 1`, which `setCurrentIndex`'s own bounds check would reject. `selectCurrentQueueTrack` returns `null`, `hasNext`/`hasPrevious` are wrong.
- **Evidence**: `state.tracks.splice(pos, 0, action.payload); if (pos <= state.currentIndex) state.currentIndex += 1;`
- **Impact**: No production caller passes a position today (`useQueueMutations.addTrack` has no UI caller after #5767), so latent; the exposed hook and `useQueue().add` would hit it.
- **Siblings**: none.
- **Related**: #4927, #5727 (backend twin: empty-queue add never syncs the pointer).
- **Suggested Fix**: Guard with `state.tracks.length > 1` (or only shift when the queue was non-empty before the insert).

### RDX-08: Write-only Redux state: `player.currentTime/duration/preset/lastUpdated` and the whole `cache` slice have no production reader or writer
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:35-42,103-110,177-186`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:149`, `auralis-web/frontend/src/store/slices/cacheSlice.ts`
- **Status**: NEW (partial overlap with #5129/#5615; closed #4921/#5354 deleted other dead actions but not these)
- **Description**: The only readers of `player.currentTime`, `player.duration` (slice field), `player.preset` and `lastUpdated` are the memoized selectors in `store/selectors/{player,combined}.ts`, which have no production consumer (#5129). Real UI reads the engine's `core.currentTime`, `currentTrack.duration` and `useEnhancementControl().preset`. That leaves two authorities for position/duration/preset: a 1 Hz `position_changed` dispatch (and snapshot writes) feed a copy nobody reads, and that copy describes the backend engine's pointer track, not the playing one (see RDX-02). `cache` has the same shape: `setCacheStats/setCacheHealth/clearCacheLocal` have no dispatch site outside the slice file and `useCacheState` has no consumer, so the slice is permanently `null/null`.
- **Evidence**: `grep -rn "setCacheStats\|setCacheHealth\|clearCacheLocal" src | grep -v store/slices/cacheSlice` is empty; `selectPreset` has no consumer.
- **Impact**: Wasted work every second (middleware chain plus, in DEV, `loggerMiddleware`'s per-action `JSON.stringify` of every slice including a large queue) and a trap: a future reader of `player.currentTime` gets the wrong track's position.
- **Siblings**: `connection` slice (#5615 open), `player.streaming.normal` (#5616 open).
- **Related**: #4921, #5129, #5354, #5615, #5616.
- **Suggested Fix**: Delete the unread fields and their dispatches (keep `lastUpdated` only if used), delete the `cache` slice or wire its producer, and drop the `position_changed` Redux write if nothing reads it.

### RDX-09: Two parallel selector sets for the same state, used interchangeably
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:244-253`, `auralis-web/frontend/src/store/selectors/player.ts:17-30`, `auralis-web/frontend/src/store/slices/queueSlice.ts:262-266`, `auralis-web/frontend/src/store/selectors/queue.ts:15-18`, `auralis-web/frontend/src/store/slices/connectionSlice.ts:191-200`, `auralis-web/frontend/src/store/selectors/connection.ts:14-20`
- **Status**: NEW
- **Description**: `selectIsPlaying/CurrentTrack/CurrentTime/Duration/Volume/IsMuted/Preset`, `selectQueueTracks/CurrentIndex`, the connection selectors and `selectCacheStats/Health` are each defined twice (slice-local with a structural state type, and again in `store/selectors/` typed on `RootState`). Production code mixes both (`Player.tsx` uses `playerSelectors.*`, `usePlayEnhanced`/`usePlaybackTransport` import the slice ones; `useQueueSubscription` imports from both). Project principle 1 (DRY).
- **Evidence**: `export const selectIsPlaying = (state: { player: PlayerState }) => state.player.isPlaying;` and `selectIsPlaying: (state: RootState) => state.player.isPlaying,` in `playerSelectors`.
- **Impact**: A field rename or a switch to a memoized form must be applied twice; no behavioural bug today.
- **Siblings**: see Location.
- **Related**: #5211, #5212.
- **Suggested Fix**: Keep one set (the `selectors/` layer) and re-export or delete the slice-local ones.

### HK-07: Two hooks hand-roll multi-type subscribe/unsubscribe effects instead of `useMessageSubscriptions`
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:94-240` (8 subscriptions in one effect); `auralis-web/frontend/src/components/playlist/usePlaylistWebSocket.ts:41-82`
- **Status**: NEW
- **Description**: Both open their own `subscribe(...)` calls and unsubscribe in the cleanup, which the checklist calls out as a finding. Behaviour is currently correct: `subscribe`, `dispatch` and `store` are stable, and `usePlaylistData` passes stable callbacks. `usePlaylistWebSocket` lists its four callbacks as effect deps, so any caller passing inline closures would resubscribe every render, which is the churn #4668 and #5621 removed elsewhere. `usePlayerStateSync` keeps its per-type watermarks in refs, so it would translate directly.
- **Siblings**: `useScanProgress.ts:232-253` and `useArtworkUpdates.ts:88-102` are deliberate refcounted module-level subscriptions and are not counted.
- **Suggested Fix**: Move both onto `useMessageSubscriptions(subscribe, handlers)`.

### HK-08: `usePlaylistData.refresh` has no out-of-order guard and nothing resyncs after a WS reconnect
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/components/playlist/usePlaylistData.ts:35-46,66-74`
- **Status**: NEW
- **Description**: Each `playlist_updated`, `playlist_created` and `playlist_deleted` event triggers `refresh()`, an unguarded `getPlaylists()` followed by `setPlaylists(response.playlists)`. Two events in quick succession (adding two tracks) start two overlapping requests, and whichever resolves last wins even if it was dispatched first. The hook has no request-id guard of the kind `useLibraryPagination` and `useLibraryQuery` use. Events missed while the socket is down are never recovered, because nothing refreshes on reconnect.
- **Impact**: The sidebar can show a stale list until the next event or a remount.
- **Suggested Fix**: Add a monotonic request id (or abort the previous request) and refresh when `connectionStatus` returns to `connected`.
- **Merged**: The API Client dimension found the same missing superseded-request guard in `hooks/enhancement/useEnhancementCommands.ts:127-129,172-175,245-248`: `setIsLoading(false)` in the `finally` of a call superseded by a newer `setPreset`/`setIntensity` clears the shared `isLoading` while the newer POST is still in flight (cosmetic).

### HK-09: `AudioPlaybackEngine.startPlayback` is re-entrant and not cancellation-safe
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:112-160,225-233`; `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:193-202`
- **Status**: NEW
- **Description**: `startPlaybackWhenBuffered` calls `engine.startPlayback()` without awaiting it, and the state only flips to `playing` after `await audioContext.resume()` (when suspended) and `await bufferScheduler.ensureReady()`. Because each engine owns a fresh `BufferScheduler` (`workletReady` is per instance), every track re-runs `audioWorklet.addModule`, and the window is real.
  - Re-entrancy: each chunk that lands inside the window issues another `startPlayback`, so `addModule` and `createProcessor` run several times.
  - Teardown race: a `stopPlayback()`/`dispose()` (Next, seek, unmount) inside the window is overtaken when the pending start resumes. It calls `createProcessor()`, `worklet.create()`, `startFeeding()`, and finally `setState('playing')` on an engine that was already stopped or disposed. The worklet node and its 50 ms feed interval are then unreachable by `dispose()` and live for the page lifetime. The buffer is disposed, so the interval only idles.
  - Pause race: a `pausePlayback()` inside the window is a no-op because `isPlaying()` is still false, so playback begins despite `pauseHoldRef`.
- **Impact**: One leaked worklet and interval per occurrence (rapid Next or seek right after first-chunk start). Stray or double starts are possible.
- **Suggested Fix**: Add a start token or disposed flag checked after each `await`, and an in-flight guard that makes concurrent `startPlayback` calls share one promise.

### HK-10: A reissue queued while disconnected bakes in a stale `start_position`
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:94-113`; `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:30-45`
- **Status**: NEW
- **Description**: When disconnected, `reissueActiveStreamAs` computes `start_position` from the resume getter at call time and pushes `next` onto the queue. On reconnect the replay loop sends that message verbatim and sets `queueHadStreamCommand`, which suppresses the normal re-issue that would recompute the position from `resumeGetters`. The engine keeps playing buffered audio during the outage, so the restart point lags the real position by the outage length.
- **Suggested Fix**: Queue the config overrides and compute `start_position` at replay time, or drop `start_position` from queued play messages so the existing `lastStreamCommand` path fills it in.

### HK-11: The auto-advance latch is set before `handleNext` reports whether it ran
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/usePlaybackSessionHooks.ts:133-137`; `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:115-145`
- **Status**: NEW
- **Description**: `useAutoAdvance` sets `hasAutoAdvancedRef.current = true` and then calls `handleNext()`. `handleNext` discards the `runTransportCommand` result (#5613 design), so if the single-flight gate is busy at that instant the advance is dropped silently and the latch stays set. It only resets when `streamingState` leaves `complete`, which does not happen on its own. The `repeat 'one'` branch goes through `startTrack`, which retries, so only the advance branch is exposed.
- **Impact**: A rare race: a Play/Pause or Next click landing exactly at track end leaves the queue stalled at the end of a finished track.
- **Suggested Fix**: Give the gate's boolean a path out of `handleNext`, or clear the latch when the command did not start.

### HK-12: Eleven exported hooks have no production caller
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useOptimisticUpdate.ts` (`useOptimisticUpdate`), `hooks/shared/useAppRedux.ts` (`useAppState`), `hooks/shared/useConnectionRedux.ts` (`useConnection`), `hooks/shared/usePlayerRedux.ts` (`usePlayerActions`), `hooks/shared/useQueueRedux.ts` (`useQueue`, `useQueueTimeRemaining`), `hooks/shared/useStandardizedAPI.ts` (`useCacheHealth`), `hooks/enhancement/useEnhancementSlices.ts` (`usePresetControl`, `useIntensityControl`, `useEnhancementToggle`), `hooks/player/usePlaybackQueue.ts` (`usePlaybackQueueView`)
- **Status**: NEW
- **Description**: A scripted search over non-test sources finds no importer outside barrels and re-export files. The enhancement slice hooks are also a trap: each call creates a full independent `useEnhancementControl` state with its own status fetch and WS subscription, which contradicts the single-source-of-truth intent. `useOptimisticUpdate` also has an unused `rollbackDelay` option and no overlap guard (a stale `previousState` rollback and out-of-order result).
- **Related**: #5778, #5036, #5392 (closed sweeps of the same kind).
- **Suggested Fix**: Delete them, or wire real callers.

### HK-13: `useAppDragDrop` branch order makes both reorder arms unreachable, and no `Draggable` exists to feed it
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:63-104`
- **Status**: NEW
- **Description**: The `destination.droppableId === 'queue'` and `startsWith('playlist-')` arms run before the `destination === source` reorder arm. A same-list drag therefore always takes the "add track" path. The "reorder within same list" code can never run, so a same-list drop would insert a duplicate rather than move. The only `@hello-pangea/dnd` usage in production is `DragDropContext` and `Droppable` (`DroppablePlaylist.tsx`), with no `Draggable` and no `queue` droppable, so the handler is currently unreachable.
- **Suggested Fix**: Check same-list first, or delete the hook together with the empty `DragDropContext`.

### TS-02: Closed string unions are redeclared inline instead of imported (the #5610 pattern, for every union except presets)
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `RepeatMode` (defined `auralis-web/frontend/src/store/slices/queueTypes.ts:9`, plus `isRepeatMode` guard) is re-typed as a literal at `services/queueService.ts:42`, `hooks/player/queueMutationGuards.ts:27`, `hooks/player/usePlaybackQueue.ts:69,95,116`, `hooks/player/useQueueMutations.ts:219`, `hooks/player/queueMutationTypes.ts:32`, `components/player/QueuePanel/QueueControlBar.tsx:6,10`, `components/player/QueuePanel/QueuePanelExpanded.tsx:16,22,126`, `types/ws/player.ts:56`, `types/ws/queue.ts:76,77` (all under `auralis-web/frontend/src/`). `StreamType` is declared twice under the same name (`store/slices/playerStreamingReducers.ts:29` and `hooks/enhancement/streamingCoreTypes.ts:26`), plus `PlaybackWireType` (`hooks/enhancement/useEnhancedPlayCommand.ts:49`) and six inline `stream_type?: 'enhanced' | 'normal'` in `types/ws/streaming.ts:47,78,126,161,172` and `types/ws/enhancement.ts:99`. `StreamingState` (`playerStreamingReducers.ts:27`) is re-typed at `contexts/playbackSessionContexts.ts:43` and `hooks/enhancement/usePlayEnhanced.ts:84`. `'play_enhanced' | 'play_normal'` appears at `contexts/WebSocketContext.tsx:87`, `hooks/websocket/useOutgoingChannel.ts:23,80`, `hooks/websocket/useWebSocketConnection.ts:61`, `hooks/enhancement/useEnhancementCommands.ts:22`.
- **Status**: NEW (the preset-only sibling #5610 is closed; the preset rule itself is respected, see TS-06 for the one bare-`string` preset prop)
- **Description**: #5610 removed the hand-mirrored preset unions; the same drift hazard remains for every other closed union. Adding a fourth repeat mode or a third stream type means editing ~15 / ~9 sites, and the compiler accepts a miss because each copy is self-consistent. `StreamType` is the sharpest case: two exported types with the same name and the same members, so an import from the wrong module compiles and the two can diverge silently.
- **Evidence**: `export type StreamType = 'normal' | 'enhanced';` in both `playerStreamingReducers.ts:29` and `streamingCoreTypes.ts:26`; `repeatMode: 'off' | 'all' | 'one';` x15.
- **Impact**: No runtime defect today. Maintainability and silent-divergence risk only.
- **Siblings**: all locations above.
- **Related**: #5610 (closed, presets only), #5823
- **Suggested Fix**: Import `RepeatMode`, `StreamType`, `StreamingState` from their one definition (keep `types/ws/*` deriving from them, as `types/ws/enhancement.ts` does for presets) and add an `OutgoingStreamCommand = 'play_enhanced' | 'play_normal'` next to the outbound message type (TS-05).

### TS-03: Hand-declared wire types omit the `| null` the backend actually sends
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/ws/base.ts:57,63` (`TrackInfo.artwork_url?: string`, `format?: string`); `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:35-43` (`year?: number`, `genre?: string`); `auralis-web/frontend/src/hooks/fingerprint/useSimilarTracks.ts:38-46` (`rank: number`, `title/artist/album: string`); `auralis-web/frontend/src/services/playlistService.ts:31` (`mastering_profile: string`); `auralis-web/frontend/src/types/ws/library.ts:112` (`current_file?: string`)
- **Status**: NEW (same class as closed #5359 and #4373)
- **Description**: The backend models declare these as nullable: `player_state.TrackInfo.artwork_url: str | None`, `.format: str | None` (default `None`, so a track with no album art serialises `"artwork_url": null` on every `player_state`/`queue_changed`); `AlbumTracksResponse.year: int | None`, `.genre: str | None`; `SimilarTrack.rank/title/artist/album: ... | None`; `Playlist.mastering_profile: Mapped[str | None]`; `ScanProgressPayload.current_file: str | None`. The frontend types say absent-or-value, never null. Every current consumer happens to be null-safe (`&&` truthiness in `AlbumMetadata`, `?? undefined` in `TrackRow`, `?? null` in `useScanProgress`), so nothing breaks today; but `?:` invites `=== undefined` checks and `.length`/`.toLowerCase()` calls that throw on `null`, which is exactly how #5359 crashed CozyLibraryView search.
- **Evidence**: backend `artwork_url: str | None = None`; frontend `artwork_url?: string;` then `mapTrackInfoToTrack` forwards it as `artworkUrl: track.artwork_url`.
- **Impact**: Latent. A future consumer written to the declared type can crash or render "null" for tracks without artwork, genre or year.
- **Siblings**: the five locations above.
- **Related**: #5131 (the opposite gap: fields omitted), #5359
- **Suggested Fix**: Declare `| null` where the backend model does (`artwork_url?: string | null`, etc.); `mapTrackInfoToTrack` can then normalise to `undefined` like `trackTransformer` does.

### TS-04: Declared fields no emitter populates: `Track.loudness`, over-wide WS `TrackInfo`, `RawPlayerStateData` gapless/crossfade, dead `transformPlayerState`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/domain.ts:45`, `auralis-web/frontend/src/api/transformers/trackTransformer.ts:61`, `auralis-web/frontend/src/api/transformers/types.ts:100` (`loudness`); `auralis-web/frontend/src/types/ws/base.ts:55-67` (`genre`, `year`, `bitrate`, `sample_rate`, `bit_depth`, `loudness`, `date_added`, `date_modified`); `auralis-web/frontend/src/types/ws/player.ts:64-78,83-113` (`gapless_enabled`, `crossfade_*`, `PlayerStateData`, `transformPlayerState`)
- **Status**: NEW (residue of closed #5524, whose fix removed `crestFactor`/`centroid` but not these)
- **Description**: `Track.to_dict()` emits `lufs_level`, never `loudness` (`routers/serializers.py:62-65` says so; `loudness` exists only on the getattr-fallback path), and no frontend code reads `track.loudness`. The WS `TrackInfo` declares eight fields the backend `TrackInfo`/`TrackPayload` (`id,title,artist,album,duration,artwork_url,format`) never sends. `RawPlayerStateData.gapless_enabled/crossfade_*` are not emitted by `PlayerStatePayload`, so `transformPlayerState` always returns its hard-coded defaults (`gaplessEnabled: true`, `crossfadeEnabled: true`, `3.0`) and has no production caller (only tests), as do `PlayerStateData`.
- **Evidence**: `types/ws/base.ts:64`: `loudness?: number;` ... `transformPlayerState(raw)` returns `crossfadeEnabled: raw.crossfade_enabled ?? true`.
- **Impact**: A false contract: a component reading these gets `undefined` or a made-up default with no error.
- **Siblings**: see Location.
- **Related**: #5524 (closed), #5131 (open, inverse gap)
- **Suggested Fix**: Narrow WS `TrackInfo` to the `TrackPayload` fields, drop `Track.loudness` (or map `lufs_level` into it), delete `PlayerStateData`/`transformPlayerState` and the three phantom state fields.

### TS-05: Client-to-server WebSocket commands are an untyped `{type: string; data?: Record<string, unknown>}`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/websocket/websocketConnectionState.ts:22-25`, `auralis-web/frontend/src/hooks/websocket/useOutgoingChannel.ts:36-119`, `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:141-156`, `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:86-92`, `auralis-web/frontend/src/hooks/enhancement/useStreamMessageHandlers.ts:146,149`
- **Status**: NEW
- **Description**: The inbound side has a discriminated registry (`AnyWebSocketMessage`, `ALL_MESSAGE_TYPES` with a compile-time exhaustiveness check). The outbound side has none: `OutgoingWebSocketMessage.type` is `string` and `data` is `Record<string, unknown>`. The command shapes (`play_enhanced {track_id, preset?, intensity?, force?}`, `play_normal {track_id, start_position?}`, `seek {track_id, position}`, `buffer_full/ready`) exist only as prose in `schemas/websocket.py`. `setResumePositionGetter(streamType: string, ...)` is keyed by bare string and looked up by command type in `replayQueueAndResume`; `reissueActiveStreamAs(..., dataOverrides: Record<string, unknown>)` is spread after `track_id`, so an override can silently clobber `track_id`, and `prevData.track_id` comes back `unknown`. A typo in `type` or a field name (`trackId`, `start_pos`) compiles and is dropped or rejected by the backend at runtime.
- **Evidence**: `export interface OutgoingWebSocketMessage { type: string; data?: Record<string, unknown>; }`
- **Impact**: No current mismatch found (all five send sites match the backend handlers), but the request half of the WS protocol has no compile-time guard while the response half does.
- **Siblings**: REST request bodies are also `Record<string, unknown>`/`any` (TS-07).
- **Related**: #5636 (inbound handler typing)
- **Suggested Fix**: Define `type OutgoingCommand = PlayEnhancedCommand | PlayNormalCommand | SeekCommand | BufferFlowCommand ...` as a discriminated union, type `send(message: OutgoingCommand)`, key resume getters by the `play_*` literal union, and make `dataOverrides` `Partial<Omit<PlayEnhancedCommand['data'], 'track_id'>>`.

### TS-06: Settings panels: `onSettingChange` key and value are independent types, and `default_preset` is written from a bare `string`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:61`; the same signature re-declared in `SettingsDialogContent.tsx:22`, `AudioSettingsPanel.tsx:17`, `AutoScanSettings.tsx:12`, `LibrarySettingsPanel.tsx:14`, `InterfaceSettingsPanel.tsx:19`, `EnhancementSettingsPanel.tsx:11`, `AdvancedSettingsPanel.tsx:21`; preset sites `EnhancementSettingsPanel.tsx:8,38,41` and `SettingsDialogContent.tsx:89` (all under `auralis-web/frontend/src/components/settings/`)
- **Status**: NEW
- **Description**: `onSettingChange: (key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate]) => void` is not generic, so `key` and `value` are unrelated: `onSettingChange('bit_depth', 'loud')` or `('theme', 42)` compiles, and any `string` is accepted for `default_preset` because `string` is in the value union (via `theme`). `EnhancementSettingsPanel` takes `defaultPreset: string` (a preset typed as bare `string`), writes `e.target.value` straight into `default_preset` without `isEnhancementPreset`, and hard-codes `<MenuItem value="adaptive">` instead of mapping `ENHANCEMENT_PRESETS`. Today the only option is `adaptive` so behaviour is correct, but this is the one UI surface that still sidesteps the single-source preset rule (`types/domain.ts`), and the backend would 422 anything else only at save time ("Failed to save settings", detail discarded).
- **Evidence**: `defaultPreset: string;` ... `onChange={(e) => onSettingChange('default_preset', e.target.value)}`.
- **Impact**: No wrong call exists today. If a second preset is ever added, the control and the type will not move together.
- **Siblings**: the 8 signature copies.
- **Related**: #5610 (closed)
- **Suggested Fix**: Make it `<K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) => void` once (export the type from `useSettingsDialog.ts` and import it in the panels), type `defaultPreset: EnhancementPreset`, and render options from `ENHANCEMENT_PRESETS`.

### TS-07: Residual production `any` outside #5377's scope: request bodies, a polymorphic ref, the custom-guard type
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:192,204,216` (`body?: Record<string, any>` on `post`/`put`/`patch`), `auralis-web/frontend/src/utils/apiRequestTypes.ts:26` (`RequestOptions.body`), `auralis-web/frontend/src/design-system/primitives/Text.tsx:102` (`ref={ref as any}`), `auralis-web/frontend/src/utils/serviceFactory.ts:110` (`custom?: Record<string, (value: unknown) => value is any>`)
- **Status**: NEW (open #5377 covers only `loggerMiddleware.ts` and `useMetadataForm.ts`; the 2026-10-16 report listed these as "not in either" and nothing was filed)
- **Description**: `useRestAPI`'s verbs already take `Record<string, unknown>` and `JSON.stringify` accepts it identically, so the `any` in the other transport buys nothing and is why `useMetadataForm` needs `updates as Record<string, unknown>` at `useMetadataForm.ts:152` while the PUT beside it takes `any`. `custom` guards typed `value is any` mean `crudService.custom<R>()`'s guard is never tied to `R` (a `SettingsResponse` guard on a call typed `custom<Foo>` compiles), which the file comment acknowledges.
- **Evidence**: `body?: Record<string, any>,` (x4) / `custom?: Record<string, (value: unknown) => value is any>;`
- **Impact**: Loss of checking on request-body construction (a misspelled body key is not an error).
- **Siblings**: #5377's two files.
- **Related**: #5377, #4664 (closed census)
- **Suggested Fix**: `Record<string, unknown>` for bodies; give `custom` a per-name generic map or accept `unknown` guards and narrow at the call; type the polymorphic ref via `React.ComponentPropsWithRef<T>['ref']`. Fold into #5377 when it is worked.

### TS-08: Casts that outlived the signature they worked around
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:100-102`; `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:53`, `auralis-web/frontend/src/hooks/player/queueMutationGuards.ts:36`; `auralis-web/frontend/src/design-system/primitives/Button.tsx:88`, `auralis-web/frontend/src/design-system/primitives/IconButton.tsx:60`; `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:83`
- **Status**: NEW (the first is a residual of closed #5639)
- **Description**: #5639 gave `WebSocketManager.on()` a mapped signature (`on<E>(event: E, handler: WebSocketEventHandlers[E])`) precisely so no cast is needed, but `attachHandlers` still wraps the message handler in `... as (event: MessageEvent | Event) => void`. The cast widens the parameter to a type the handler cannot actually accept (it reads `MessageEvent` fields) and defeats the check #5639 added; removing it compiles. The two `useStore() as Store<RootState>` casts duplicate what `usePlayerRedux.ts:39` does with `useStore<RootState>()`. In `Button`/`IconButton` the `default:` arm's `size` is already narrowed to `'sm'|'md'|'lg'`, so `as` is a no-op that hides future union growth. `transformTracks(...) as DetailTrack[]` widens a `Track[]` to a `Pick` of itself and needs no cast.
- **Evidence**: `manager.on('message', ((event: MessageEvent) => {...}) as (event: MessageEvent | Event) => void);`
- **Impact**: None at runtime; each cast would hide a real type error if the surrounding types changed.
- **Siblings**: all locations above.
- **Related**: #5639 (closed)
- **Suggested Fix**: Delete the casts; use `useStore<RootState>()` at the two store sites.

### TS-09: `useLibraryQuery<T>`'s result type is not tied to `queryType`; `extractItemsFromResponse` forces `as T[]`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:59-62`, `auralis-web/frontend/src/hooks/library/libraryQueryRequest.ts:83-106`, `auralis-web/frontend/src/hooks/library/useLibraryQueries.ts:73-77`
- **Status**: NEW
- **Description**: `useLibraryQuery<T extends Track | Album | Artist = Track>(queryType: LibraryQueryType, ...)` takes `T` and `queryType` as independent parameters, and `extractItemsFromResponse<T>` returns `transformTracks(...) as T[]` / `transformAlbums(...) as T[]` / `transformArtists(...) as T[]`. `useLibraryQuery<Album>('tracks')` therefore type-checks and returns `Track[]` at runtime. The three convenience wrappers pair them correctly, only `useArtistsQuery` has a production caller (`CozyArtistList.tsx:54`), and `useInfiniteScroll<T>(queryType, ...)` (zero production callers) re-exposes the free pairing.
- **Evidence**: `return transformAlbums((r.albums ?? r.items ?? []) as AlbumApiResponse[]) as T[];`
- **Impact**: Latent; today's callers are correct.
- **Siblings**: `useInfiniteScroll`.
- **Related**: none
- **Suggested Fix**: Use a type map `{ tracks: Track; albums: Album; artists: Artist }` and `useLibraryQuery<Q extends LibraryQueryType>(queryType: Q): UseLibraryQueryResult<Items[Q]>`, or delete the unused generic wrapper.

### DS-04: Hex-alpha suffix appended to `var(--app-*)` strings produces invalid CSS; 7 more sites bypass `opacityScale` with `#RRGGBBAA` concatenation
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/CozyLibraryView/LibrarySearchControls.tsx:50`, `auralis-web/frontend/src/design-system/primitives/Input.tsx:95`, `auralis-web/frontend/src/components/shared/feedback/ProcessingStatsChips.tsx:74`
- **Status**: NEW (distinct from #5644, which is `px` appended to a `px` token; no issue covers the hex-suffix class)
- **Description**: `themeVars.*` values are `var(--app-...)` strings (and in dark mode several resolve to `rgba(...)`), so appending a two-digit hex alpha yields `var(--app-surface-raised)80`, which is an invalid declaration and is dropped by the browser. The intended translucency never applies.
- **Evidence**:
```tsx
// LibrarySearchControls.tsx:50
background: `${themeVars.surfaceRaised}80`,            // -> "var(--app-surface-raised)80"  invalid
// Input.tsx:95
? `0 0 12px ${themeVars.error}20`                        // invalid box-shadow
// ProcessingStatsChips.tsx:74
backgroundColor: `${themeVars.textSecondary}1A`,         // invalid
```
- **Impact**: The library search/controls bar renders the plain MUI Paper surface instead of the intended 50% raised glass (the `backdropFilter: blur(10px)` then blurs nothing). The other two sites are in dead code today (`Input` per #5132; `ProcessingToast` / `ProcessingStatsChips` have no importers), so they are latent.
- **Siblings**: valid-but-token-bypassing 8-digit hex concatenation on hex tokens (should be `tokens.colors.opacityScale.*` or `withOpacity`): `components/shared/ConnectionDetailsPanel.tsx:215` (`error}20`), `components/shared/EnhancementToggle/EnhancementToggleStyles.ts:18,26` (`primary}15`, `}25`), `components/library/Details/ArtistDetailTabs.tsx:44` (`primary}40`), `components/shared/ui/ThemeToggleIcon.tsx:28` (`warning}99`), `components/shared/feedback/ProcessingStatsChips.tsx:42,58` (`}1A`).
- **Related**: #5644, #4464 (closed: hex->rgba helper duplication)
- **Suggested Fix**: Use `color-mix(in srgb, ${themeVars.x} 50%, transparent)` (already the idiom at `DropZoneStyles.ts:30` and `TrackTableHeader.tsx:18`) for `var()` colours and `tokens.colors.opacityScale.*` / `withOpacity()` for hex tokens; add a source-grep test beside `darkOnlyTokenLeak.test.ts` forbidding `\}[0-9a-fA-F]{2}` after a `themeVars`/`tokens.colors` interpolation.
- **Merge note**: `LibrarySearchControls` is not imported anywhere in production (it is on the #5628 orphan list), so all three `var(...)NN` sites are latent today, not just the last two. The class is still worth a guard test because the pattern compiles and fails silently in the browser.

### DS-05: Residual white-alpha / dark-glass fills on themed surfaces vanish or lose contrast in light mode
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/design-system/primitives/SegmentedControl.tsx:72-77,108,125`; `auralis-web/frontend/src/components/shared/EnhancementToggle/EnhancementToggleStyles.ts:70-72`; `auralis-web/frontend/src/components/playlist/DroppablePlaylist.styles.ts:26`; `auralis-web/frontend/src/components/library/Views/TrackListView.styles.ts:6`; `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:55`; `auralis-web/frontend/src/components/library/Styles/Button.styles.ts:45,97`; `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:37,61`; `auralis-web/frontend/src/components/settings/FingerprintCoverageCard.tsx:56`
- **Status**: Regression of #5641 (its completeness-check siblings `EnhancementToggleStyles.ts:70-72`, `AlbumsTab.tsx:55`, `TrackListView.styles.ts:6`, `Button.styles.ts:45,97` are all still present; closure fixed only the five headline surfaces)
- **Description**: Backgrounds, borders and hover tints built from `opacityScale.white.*` (3-15% white) or `tokens.glass.subtle` (25% dark navy) are dark-theme primitives. On the light palette (`#FFFFFF` / `#F8F9FD`) white-alpha is invisible and the navy tint turns into a grey wash under text that was already switched to dark ink.
- **Evidence**: `SegmentedControl`: container `white.ultraLight` (3%) + border `white.faint` (6%); selected segment `white.subtle` (8%), so selected vs unselected differs only by text colour. `Button.styles` disabled state: `color: opacityScale.white.veryStrong` on `accent.strong` is 1.22:1 in light mode. `ScanStatusCard`/`FingerprintCoverageCard` spread `tokens.glass.subtle` (25% navy over white = `#C4C6CB`): `textSecondary` `#5A6280` is 3.5:1 and `textMuted` shares that value (AA needs 4.5:1).
- **Impact**: Light mode only: no hover/selected feedback on `DroppablePlaylist` rows and `SegmentedControl` (the library view switcher in `LibraryViewRouter`), invisible card/paper chrome on the toggle and empty states, near-illegible disabled dialog buttons, sub-AA secondary text on two settings cards. Mostly cosmetic.
- **Siblings**: see Location (9 files); `design-system/primitives/List.tsx:30`, `components/library/Styles/ArtistList.styles.ts:46,55,111` use the same white-alpha for hairlines (harmless but also invisible).
- **Related**: #5641, #5675
- **Suggested Fix**: Add `selectedFill` / `hoverFill` / `hairline` roles to `SemanticTheme` (dark = current white-alpha, light = dark-alpha or accent-soft) and consume them from these sites; extend the `darkOnlyTokenLeak` sweep to `opacityScale.white` and `tokens.glass.subtle` outside the mapping layer.

### DS-06: Theme is applied in `useEffect` (first paint is always dark) and `globalStyles` re-types 28 of the 34 `--app-*` defaults by hand
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/contexts/ThemeContext.tsx:43-55`, `auralis-web/frontend/src/styles/globalStyles.ts:15-60`, `auralis-web/frontend/index.html`
- **Status**: NEW
- **Description**: (a) The saved mode is read synchronously (`useState` initialiser), but `data-theme`, `colorScheme` and every `--app-*` custom property are written in a passive `useEffect`, i.e. after the first paint, and `globalStyles` `:root` hard-codes `color-scheme: dark` plus the dark values; `index.html` has no pre-hydration theme script. A user with `auralis-theme=light` therefore gets a dark flash on every launch. (b) The `:root` block lists the 28 oldest variables manually from `getSemanticTheme('dark')` instead of spreading `getSemanticCssVariables('dark')`, so six contract variables have no default: `--app-menu-surface`, `--app-glass-fill-strong`, `--app-glass-fill`, `--app-glass-fill-hover`, `--app-switch-thumb`, `--app-switch-track` (consumers: `BatchActionsMoreMenu`, `AddToPlaylistMenu`, `SimilarTracksModal`, `TrackCardOverlay`, `SwitchVariant`). Anything rendering before the effect, or outside `ThemeProvider`, resolves them to `unset`. `cssCustomPropertyProducers.test.ts` states `getSemanticCssVariables()` is the only producer, which `globalStyles.ts` contradicts.
- **Evidence**:
```ts
// ThemeContext.tsx:43-55
useEffect(() => { ...; root.dataset.theme = mode; Object.entries(getSemanticCssVariables(mode)).forEach(...setProperty) }, [mode]);
// globalStyles.ts -- 28 hand-written lines, none of the six roles added by #5641:
--app-canvas: ${defaultTheme.canvas}; ... --app-shadow-overlay: ${defaultTheme.shadowOverlay};
```
- **Impact**: Visible light-to-dark flash at startup for light-mode users; latent drift each time a role is added to `SemanticTheme` (it already happened once, with #5641).
- **Siblings**: `--gradient-aurora`, `--gradient-aqua`, `--glow-accent-*`, `--glow-aqua-*` (`globalStyles.ts:49-56`) have zero consumers (grep for `var(--glow-` / `var(--gradient-` is empty).
- **Related**: #4535 (closed, same producer-contract theme)
- **Suggested Fix**: Generate the `:root` block from `Object.entries(getSemanticCssVariables('dark'))`, apply the theme in `useLayoutEffect` (or a tiny inline script in `index.html` that sets `data-theme` and the variables before first paint), and drop the unused `--gradient-*` / `--glow-*` variables.

### DS-07: Custom `::-webkit-scrollbar` styling is dead under Electron's Chromium; only `scrollbar-color` applies
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/styles/globalStyles.ts:87-111`
- **Status**: NEW
- **Description**: The global style sets both the legacy `::-webkit-scrollbar*` pseudo-elements (10px width, rounded thumb, 2px inset border, accent on hover) and the standard `* { scrollbar-width: thin; scrollbar-color: ... }`. Since Chromium 121 a non-`auto` `scrollbar-width`/`scrollbar-color` disables the `::-webkit-scrollbar` pseudo-elements entirely. The desktop shell pins `electron ^43.7.6` (`desktop/package.json:32`), well past that. The webkit block, including the accent hover colour and the rounded thumb, therefore never renders in the shipped app; the visible scrollbar is the UA's thin bar with the two flat colours (and, per DS-02, invisible in light mode).
- **Evidence**: `globalStyles.ts:97-110` (`::-webkit-scrollbar-thumb { border-radius: full; border: 2px solid ... } ::-webkit-scrollbar-thumb:hover { background: accent }` followed by `* { scrollbar-width: thin; scrollbar-color: ... }`).
- **Impact**: Design intent (rounded thumb, accent hover) silently unrealised; maintenance cost of dead rules. No functional break.
- **Related**: DS-02
- **Suggested Fix**: Keep only the standard properties (and fix the colours per DS-02), or drop `scrollbar-width/-color` if the custom webkit look is wanted.

### DS-08: MUI theme breakpoints are not derived from `tokens.breakpoints`; CSS `max-width: 900px` and MUI `down('md')` disagree at the boundary
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:17-35`, `auralis-web/frontend/src/components/player/Player.styles.ts:46,62,75`, `auralis-web/frontend/src/components/library/Details/DetailViewHeader.tsx:54,66`, `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts:224`, `auralis-web/frontend/src/hooks/app/useAppLayout.ts:51-53`
- **Status**: NEW (the spacing twin, #5384, is closed; its breakpoint equivalent was not done)
- **Description**: `createAuralisTheme` derives MUI's spacing unit and radius from tokens but omits `breakpoints`, so MUI keeps its own defaults. They match `tokens.breakpoints` numerically today (600/900/1200/1536), but are two sources of truth. Responsive logic is also split across two idioms with different boundary semantics: JS (`useMediaQuery(theme.breakpoints.down('md'))`, in `useAppLayout`, `AppSidebar`, `AppTopBar`) is true below 899.95px, while the CSS rules use `@media (max-width: ${tokens.breakpoints.md})`, true up to and including 900px. At exactly 900px the sidebar logic says desktop while `Player`, `DetailViewHeader` and `TrackRow` apply their mobile rules.
- **Impact**: Retuning `tokens.breakpoints` silently desynchronises the layout hook from the CSS; a one-pixel layout inconsistency at 900px. Low value for a desktop-only app, but it is the design system's responsive contract.
- **Suggested Fix**: Pass `breakpoints: { values: { xs: 0, sm: parseInt(tokens.breakpoints.sm), ... } }` to `createTheme` (a pinning test like the #5384 one) and use `theme.breakpoints.down('md')` string helpers (or `calc(<md> - 0.05px)`) in the CSS-in-JS rules.

### DS-09: Typography tokens name fonts the app does not ship (Asap via Google CDN, JetBrains Mono never loaded, Material Icons CSS unused)
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/index.html:13-25`, `auralis-web/frontend/src/design-system/tokens/typography.ts:14-17`
- **Status**: NEW
- **Description**: `tokens.typography.fontFamily.primary` is `Asap, "Segoe UI", sans-serif`, delivered only by a runtime `<link>` to `fonts.googleapis.com` (the backend CSP explicitly allows that origin). Auralis is a local desktop app that must work offline, where Asap is absent and the fallback `Segoe UI` does not exist on Linux/macOS, so the design-language font becomes the platform `sans-serif`. `fontFamily.mono` (`'JetBrains Mono', 'Courier New', monospace`, 6 production uses for dB/Hz/LUFS readouts) is not loaded anywhere (no `@font-face`, no link, no package), so it always falls to `Courier New`. The `Material Icons` stylesheet is requested on every launch but nothing uses the icon font (all icons are `@mui/icons-material` SVG; no `material-icons` class in `src/`).
- **Evidence**: `index.html` links `family=Asap:...&display=swap` and `icon?family=Material+Icons`; `grep -rn "font-face\|JetBrains" src` finds only the token string.
- **Impact**: Offline or first-launch-before-network: typography differs from the design language and layouts tuned to Asap metrics reflow when it arrives; mono readouts never use the intended face; two needless third-party requests (privacy and startup latency) from a localhost app.
- **Related**: #2419 (closed, SRI on those links), #3127 (closed, fonts overriding Asap)
- **Suggested Fix**: Bundle Asap and JetBrains Mono (`@fontsource-variable/*` or local `@font-face` in `globalStyles`), drop the Material Icons link, and then drop `fonts.googleapis.com` / `fonts.gstatic.com` from the CSP.

### DS-10: Production-style `../../` relative imports are back in 20 test files (`vi.mock` paths)
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/contexts/__tests__/WebSocketContext.{ping,reconnect,cacheCleared,unregisteredType,mountedRef,audioChunk}.test.tsx` (`vi.mock('../../utils/errorHandling', ...)`), `components/library/__tests__/{TrackRow,CozyArtistList,TrackListView,GlobalSearch,AlbumDetailView,LibraryEmptyState,useBatchOperations,useMetadataEditing}.test.*`, `components/__tests__/ThemeToggle.test.tsx`, `services/__tests__/{queueService,settingsService}.test.ts`, `components/settings/__tests__/SettingsDialog.test.tsx` (`../../../`), `components/library/Items/tracks/__tests__/{TrackRowMemoization,TrackRow.artworkCacheBust}.test.tsx`
- **Status**: Regression of #4466 (closed 2026-08-22 by `790cfa95`, "convert ../.. relative imports to @/ alias in 20 test files"; the same count has accumulated again)
- **Description**: Production code is clean (the only `../` in non-test `src/` is inside `test/TEMPLATE.example.tsx`), but 27 `../..` specifiers across 20 test files remain, all in `vi.mock`/`importOriginal` calls. `@/` resolves identically in vitest (alias in `vitest.config.ts:24`) and is the project rule. The legitimate exceptions (`__tests__/viteChunking.test.ts` reaching the frontend root, and the `import.meta.glob('../../**')` scans) are excluded from this count.
- **Impact**: Convention drift; a moved file silently stops matching its `vi.mock` string. No runtime effect.
- **Related**: #4466, #4205, #2829
- **Suggested Fix**: Convert to `@/...` and add an ESLint `no-restricted-imports` pattern (`../../*`) so it cannot return.

### DS-11: Dead styling assets: 10 utility classes + 7 keyframes in `globalUtilities/globalKeyframes`, 7 unused token groups, an unused feedback component pair
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/styles/globalUtilities.ts:9-83`, `auralis-web/frontend/src/styles/globalKeyframes.ts` (`glow`, `shimmer`, `slideInUp`, `scaleIn`, `fadeIn`, `fadeInDown/Left/Right`), `auralis-web/frontend/src/design-system/tokens/{effects,semantics,layout}.ts`, `auralis-web/frontend/src/components/shared/feedback/{ProcessingToast,ProcessingStatsChips}.tsx`
- **Status**: NEW (the #5841 split moved this code verbatim; neither #5216 nor #5420 covered it)
- **Description**: Production references (excluding tests and `styles/global*`): the only utility class used anywhere is `animate-fade-in-up` (`TrackGridView.tsx:95`) plus `app-ambient-background`. Dead: `.gradient-text`, `.animate-fade-in/-down/-left/-right`, `.animate-scale-in`, `.hover-lift`, `.hover-scale`, `.smooth-transition`, `.glow-effect`, `.pulse-effect`, `.skeleton`; likewise the keyframes only they use. `tokens.{visualization,numbersPolicy,audioReactive,elevation,opacity,blur,animations}` have zero production consumers (`tokens.animations` additionally embeds `@keyframes pulse/fadeIn/slideUp` strings that nothing injects). Unreferenced leaves include `lightMode.neon`, `text.inverse`, `utility.{hoverBg,activeBg,focusRing,focusGlow,successBg}`, `gradients.{auroraSoft,auroraVertical,glassViolet,glassAqua,glassMesh,borderGlow,overlay}`, `glass.{violet,aqua}`, `audioSemantic.harmonicDark`. `components/shared/feedback/ProcessingToast.tsx` and `ProcessingStatsChips.tsx` have no importers outside their own test (they are also the source of DS-04's `ProcessingStatsChips` hit and a third `pulse` definition).
- **Impact**: Maintenance and drift surface (these are the definitions that DS-03 collides with); the design system advertises affordances nothing uses. No runtime effect.
- **Related**: #5216, #5420, #4402 (same sweeps on other token blocks), #5132 (dead primitives)
- **Suggested Fix**: Delete the dead classes, keyframes and token groups; verify with a grep before removal and drop the matching tests.

### API-03: Response guards are unreachable on the production albums path; most other `get()` call sites cast the JSON
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/api/responseGuards.ts:84-92`; `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:46-52`; `auralis-web/frontend/src/hooks/library/libraryQueryTypes.ts:100-104`; `auralis-web/frontend/src/hooks/library/useLibraryQueries.ts:25-52`
- **Status**: NEW
- **Description**: `isAlbumsListShape` is wired only into `useLibraryQuery('albums')` (`QUERY_TYPE_GUARD`), reached via `useAlbumsQuery`/`useTracksQuery`. `grep` finds no production consumer of `useAlbumsQuery` or `useTracksQuery` (only `useArtistsQuery` in `CozyArtistList`). The albums grid that users actually see goes through `useInfiniteAlbums`, which calls `get<AlbumsApiResponse>(url)` with no `validate` and then runs `transformAlbumsResponse(apiResponse)`, which dereferences `apiResponse.albums.map(...)` unguarded. The guard therefore implies coverage of `GET /api/albums` that the real path does not have. Other `get`/`post` call sites that cast without a guard: `useAlbumDetails` (`/api/albums/{id}/tracks`, then `data.tracks ?? []`, `data.total_tracks`), `useArtistDetailsData` (`/api/artists/{id}`), `useSimilarTracks`, `useSearchLogic` x3, `useLibraryStats`, `useTrackFingerprint`/`useAlbumFingerprint` (`data.fingerprint`), `addTracksToPlaylist` (`data.added_count`), `addTracksToQueue`, `createPlaylist` (declared `Promise<PlaylistWire>` by the CRUD factory although the backend answers the `{message, playlist}` envelope; no `guards.create`, and the "bare Playlist" fallback branch in `playlistService.createPlaylist` handles a shape the backend never emits).
- **Evidence**:
  ```ts
  // useInfiniteAlbums.ts
  return get<AlbumsApiResponse>(`/api/albums?${params}`);        // no { validate: isAlbumsListShape }
  // albumTransformer.ts
  albums: transformAlbums(apiResponse.albums),                    // TypeError if the key is renamed
  ```
- **Impact**: Backend drift on `/api/albums` surfaces as a `TypeError: Cannot read properties of undefined (reading 'map')` inside the queryFn (rendered as a generic error) instead of the located "Unexpected response shape from /api/albums" message the guard exists to give.
- **Siblings**: see Description list.
- **Related**: #4607 (closed; guard introduction), #5637.
- **Suggested Fix**: Pass `validate: isAlbumsListShape` in `useInfiniteAlbums` (the predicate already narrows to `AlbumsApiResponse`); add guards for album-tracks/artist-detail/createPlaylist; delete `useAlbumsQuery`/`useTracksQuery` or the dead branch if they stay unused.

### API-04: Fingerprint hooks carry their own retry rule and re-typed durations; one transient error permanently stops `useTrackFingerprint` polling
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:85-110`; `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:88-107, 146-160`; `auralis-web/frontend/src/hooks/fingerprint/similarityCache.ts:42`
- **Status**: NEW
- **Description**: The project rule is that `shouldRetryQuery` is the single retry policy (App.tsx default). Three queries override it with `retry: false`. In `useTrackFingerprint` the stated reason ("Don't retry on 404") is obsolete: since #4847 a 404 resolves to `null` and never reaches the retry logic, and `shouldRetryQuery` would not retry a 4xx anyway. What `false` actually suppresses is the one allowed retry of a transport failure/5xx. Worse, the same hook's `refetchInterval` returns `false` once `query.state.status === 'error'`, so a single timeout/503 during the 5 s "queued, not ready" polling loop (which runs while the backend is busy fingerprinting, i.e. when slow responses are likely) ends polling permanently; the pane stays on "pending" with no further requests until the track changes. The album hooks document `retry: false` as a settled decision (tile art is decorative), so they are listed as siblings, not as defects. Durations are also re-typed rather than shared via `config/timing.ts`: `gcTime: 30 * 60 * 1000` three times, the `5000` default `retryInterval`, and `similarityCache.CACHE_TTL_MS = 5 * 60 * 1000`, which is `QUERY_STALE_TIME_MS` spelled again (#5800 collapsed the other copies; a test pins `staleTime` literals out but not these).
- **Evidence**:
  ```ts
  staleTime: QUERY_STALE_TIME_MS, gcTime: 30 * 60 * 1000, enabled,
  retry: false, // Don't retry on 404
  refetchInterval: (query) => { if (query.state.status === 'error') return false; ... }
  ```
- **Impact**: Fingerprint/character pane never appears for a track after one transient failure mid-poll (workaround: change track). Duration drift risk only.
- **Siblings**: `useAlbumFingerprint.ts:105`, `useAlbumFingerprints` `retry: false` at :158.
- **Suggested Fix**: Drop `retry: false` from `useTrackFingerprint` (let `shouldRetryQuery` decide) and let polling continue through a transient error (return `retryInterval` unless `error.statusCode` is a non-retryable 4xx); add `QUERY_GC_TIME_MS` to `config/timing.ts` and reuse `QUERY_STALE_TIME_MS` for the similarity cache TTL.

### API-05: `apiRequest` reports a malformed 2xx body (and any non-APIRequestError throw) as `statusCode 0` "Network error", which `shouldRetryQuery` retries and the UI shows as "Failed to connect"
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:130-147, 216-222`; `auralis-web/frontend/src/utils/queryRetry.ts:16-38`; `auralis-web/frontend/src/hooks/library/libraryPageFetch.ts:63-71`; `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:42-48`
- **Status**: NEW (sibling of open #5653, which covers only the abort wrapping/documentation)
- **Description**: `queryRetry.ts` documents `status 0` as "apiRequest's code for a transport failure before any response (timeout or network error)". But the `catch` in `apiRequest`/`getBlob` wraps *every* non-`APIRequestError` throw as `APIRequestError('Network error: ...', 0)`, which includes `response.json()` failing on a 200 with an empty/HTML body (`SyntaxError`), `response.blob()` failures, and caller aborts. Consumers that key on `statusCode === 0` therefore misclassify: `shouldRetryQuery` spends its retry on a deterministic parse failure; `friendlyFetchError` tells the user "Failed to connect to server" for a server that answered; `useAPIHealthPoll` marks the API *disconnected* (and latency 0) when `/api/health` answers 200 with a non-JSON body, contradicting its own comment that "a backend that answers at all is reachable".
- **Evidence**:
  ```ts
  const parsed: unknown = await response.json();      // SyntaxError on empty/HTML 200
  ...
  } catch (error) { if (error instanceof APIRequestError) throw error;
    throw new APIRequestError(`Network error: ${message}`, 0, message); }
  ```
- **Impact**: Wrong message/retry on a rare contract break; health indicator flips to disconnected on a bad-body 200.
- **Siblings**: `getBlob` (same catch).
- **Related**: #5653.
- **Suggested Fix**: Wrap only the `fetchWithTimeout` call in the status-0 conversion; map a body-parse failure to `APIRequestError('Invalid response body', response.status)` so the existing "anything else, including a 200 that failed the response-shape check: not retryable" rule applies.

### API-06: After #5841 two timeout-fetch implementations remain, and the transport docs still describe the pre-split world
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/api/restApiTransport.ts:1-70`; `auralis-web/frontend/src/utils/apiRequest.ts:1-60`; `auralis-web/frontend/src/utils/apiRequestTypes.ts:6-12`
- **Status**: NEW
- **Description**: Behaviour of the split is preserved (verified against 61ad7103), but the duplication it was meant to reduce is untouched: `restApiTransport.fetchWithTimeout` and `apiRequest.fetchWithTimeout` each implement the `didTimeout` flag, the `APIRequestError(..., 0)` mapping and the clear-timer `finally` (the former's comment says "Mirrors utils/apiRequest.ts's identical mapping"). They have already diverged: the REST one cannot take a caller `signal` or a per-request timeout, and `useRestAPI` throws `HttpStatusError` (`.status`) while `apiRequest` throws `APIRequestError` (`.statusCode`), so `isRetryableError`'s status path only applies to one of them (`ApiErrorHandler.parse` has to read both property names). `restApiTransport` also imports `DEFAULT_TIMEOUT_MS`/`APIRequestError` through the `@/utils/apiRequest` re-export instead of `apiRequestTypes`, the module now documented as their home. `apiRequest.ts`'s header still says it "Mirrors the pattern in standardizedAPIClient" (deleted, #4693) and describes `useRestAPI` as an un-split duplicate that "reimplements the transport"; `apiRequestTypes.ts` says useRestAPI "uses the same 30s" when it imports the constant.
- **Evidence**:
  ```ts
  // restApiTransport.ts
  let didTimeout = false; const timeoutId = setTimeout(() => { didTimeout = true; controller.abort(); }, DEFAULT_TIMEOUT_MS);
  // apiRequest.ts  (same shape, again)
  let didTimeout = false; const timeoutId = setTimeout(() => { didTimeout = true; controller.abort(); }, timeoutMs);
  ```
- **Impact**: Maintenance only; the next timeout fix must be made twice (the #5609 fix already was).
- **Siblings**: n/a.
- **Suggested Fix**: Export `fetchWithTimeout` from `apiRequest.ts` (it already supports `callerSignal`) and have `restApiTransport` call it with a controller-forwarding signal; error type unification (`HttpStatusError` vs `APIRequestError`) can follow. Refresh the two stale doc blocks either way.

### API-07: Backend-provided artwork URLs are used verbatim (relative) while `getArtworkUrl` prefixes `API_BASE_URL`
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/artworkService.ts:44-47, 56-76`; `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:112`; `auralis-web/frontend/src/components/track/TrackCard.tsx:68`; `auralis-web/frontend/src/components/player/Player.tsx:143`; `auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx:54`
- **Status**: NEW (adjacent to open #5654 but a different seam: that issue is the WS URL and the `ENDPOINTS` catalog)
- **Description**: Album art is built with `getArtworkUrl()` -> `${API_BASE_URL}/api/albums/{id}/artwork`. Track and player artwork comes from the transformer's `artworkUrl` (the backend's `/api/albums/{id}/artwork` string) and is passed to `<img src>` as-is, with `withArtworkSize` deliberately returning the relative path unchanged. In a production build the page is served by the backend so the relative form resolves; whenever `API_BASE_URL` points at a different origin (the `VITE_API_URL` escape hatch from #4468, or `pnpm dev` with an override) album tiles load and track rows/player/artist header art 404 against the page origin. Only one of the two forms honours the "base URL comes from `config/api.ts`" rule.
- **Evidence**:
  ```ts
  // artworkService.getArtworkUrl: return `${API_BASE_URL}/api/albums/${albumId}/artwork...`
  // withArtworkSize: if (!url.startsWith('/api/')) return url; ... return `${url}${separator}${query}`  // still relative
  ```
- **Impact**: Mixed artwork success only under a non-same-origin API base; none in the default configurations (note the Vite dev proxy target is also hard-coded to 8765).
- **Siblings**: `TrackDisplay.tsx:143`, `MediaCardArtwork.tsx:112` (consumers of the raw string).
- **Suggested Fix**: Resolve backend-relative artwork paths once, in the transformers or in `withArtworkSize`, via `getApiUrl()`.

### PERF-04: ComfortableApp re-renders the whole shell on every volume change; Sidebar memo and AppTopBar are defeated
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:64,142,144,149-153`
- **Status**: NEW
- **Description**: ComfortableApp subscribes to `selectVolume` only to compute the keyboard volume +/-10 step (`useAppShortcuts`). The Player's volume slider is a native range input whose `onChange` fires per input event and dispatches `setVolume` (PlaybackSession `handleVolumeChange`), as does WS `volume_changed`. Each dispatch re-renders ComfortableApp. It passes fresh inline arrows (`onToggleCollapse`, `onOpenSettings`, `onOpenMobileDrawer`, `onSearchClear`) to `AppSidebar`/`AppTopBar`, which defeats `Sidebar`'s `memo`. `AppTopBar` is not memoized at all.
- **Evidence**:
  ```tsx
  const volume = useSelector(selectVolume);   // ComfortableApp.tsx:64
  <AppSidebar onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
              onOpenSettings={() => setSettingsOpen(true)} ... />
  ```
- **Impact**: While dragging the volume slider, the sidebar, top bar (search input, view toggle) and the shortcut-array rebuild all re-render at pointer-event rate. This is the same class as #5006, which was fixed for the 10Hz tick but not for volume. The cost is modest because `CozyLibraryView` is memoized.
- **Siblings**: `Player.tsx:46-47` and `usePlayEnhanced.ts:161-162` also subscribe to volume, but those consumers legitimately need it.
- **Related**: #5006, #4632 (closed).
- **Suggested Fix**: Read volume lazily in the shortcut handler (`store.getState().player.volume`, or a ref) instead of subscribing. Wrap the four callbacks in `useCallback` and `memo` `AppTopBar`.

### PERF-07: Player-bar artwork requests the full-resolution image for a 44x44 element
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:143`; `auralis-web/frontend/src/components/player/TrackDisplay.tsx:141-154`
- **Status**: NEW (sibling gap of closed #4447/#4901, which covered TrackRow, TrackCard and the album cards)
- **Description**: Every other thumbnail consumer routes through `withArtworkSize()`/`getArtworkUrl({size})`, so the backend serves a bucketed downscale. `Player` passes `currentTrack.artworkUrl` raw to `TrackDisplay`, which renders it as a fixed 44x44 `<img>` with no `loading`/`decoding` hint and no `size`/`v` parameters. The browser fetches and decodes the full-resolution cover, which can be several MB, on each track change. The URL also carries no `artwork_updated` revision, so a refreshed cover is not cache-busted here, unlike the list views (#5473).
- **Evidence**: `<TrackDisplay artworkUrl={currentTrack?.artworkUrl} />` with `withArtworkSize` absent from Player.tsx and TrackDisplay.tsx.
- **Impact**: Extra bandwidth/decode and memory on every track change, and a stale cover after an artwork update.
- **Siblings**: `components/library/Details/ArtistHeader.tsx:42-64` renders an external CDN URL directly (intentional, #4526).
- **Related**: #4447, #4901, #5473 (closed).
- **Suggested Fix**: Use `withArtworkSize(currentTrack?.artworkUrl, 88, revision)` (2x for HiDPI) in Player or TrackDisplay.

### A11Y-09: Playing/current track is conveyed visually only in library track lists
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:117-123` (and `TrackRow.styles.ts:28`); `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:54-60`; `auralis-web/frontend/src/components/library/Views/ArtistTrackRow.tsx:31-35`
- **Status**: NEW
- **Description**: `aria-current` exists for the sidebar (`NavigationSection.tsx:35`) and the queue (`QueueTrackItem.tsx:60`) only. The library listbox option (`aria-label="{title} by {artist}"`, which replaces the option's content for AT), the album-detail table rows and the artist-detail table rows mark the current/playing track with an accent colour, an active indicator and an icon swap, none of which is exposed. `aria-selected` on the listbox option means batch selection, not playback.
- **Evidence**: `grep -rn "aria-current" src --include=*.tsx | grep -v test` lists three files, none a library row.
- **Impact**: A screen-reader user moving through the track list cannot tell which row is playing (the Player region announces the track only on change).
- **Suggested Fix**: Add `aria-current={isCurrent ? 'true' : undefined}` to the three row elements and append "now playing" to the option label.

### A11Y-10: The track listbox's roving tab stop can point at an unmounted row, leaving the list with no tab stop
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:58-61,90-96,228`
- **Status**: NEW
- **Description**: `tabIndex={virtualRow.index === activeIndex ? 0 : -1}` assumes the active row is mounted. The list is virtualized (window plus overscan 10) and driven by the app-level scroll container, so after the user scrolls with the wheel/scrollbar (or Page keys) away from `activeIndex` (initially 0), the row holding `tabIndex=0` is unmounted and every mounted row has `tabIndex=-1`. Tab then skips the whole listbox. The clamp effect only handles shrinking lists. Focused-row unmount also drops focus to `<body>`. (Mixed pointer-then-keyboard use; inferred from the code, not run.)
- **Impact**: After scrolling, a keyboard user cannot Tab into the library list until they scroll back to the remembered row or click a row.
- **Suggested Fix**: When `activeIndex` is outside `virtualItems`, give the first mounted row `tabIndex=0` (or track the roving index against visible rows).

### A11Y-11: Sidebar and queue collapse toggles strand keyboard focus
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/layouts/Sidebar/Sidebar.tsx:35-46`; `auralis-web/frontend/src/components/layouts/Sidebar/CollapsedSidebar.tsx`, `SidebarHeader.tsx:29-33`; `auralis-web/frontend/src/components/player/Player.tsx:198-216`; `auralis-web/frontend/src/components/player/QueuePanel/QueuePanelExpanded.tsx:174-184`
- **Status**: NEW
- **Description**: Activating "Collapse sidebar" swaps `<SidebarContainer>` for a different component tree (`CollapsedSidebar`), so the focused button is unmounted rather than updated and focus falls to `<body>` (the matching "Expand sidebar" button is a different element). The same happens in reverse. In the Player, the "Collapse queue panel" button inside the queue sets the wrapper to `display: none` while it holds focus, so focus is lost and is not returned to the "Toggle queue" button that opened it. (`PlaybackControls`'s play/pause swap is fine: both branches are `<button>` at the same position, so React reuses the node.)
- **Impact**: Each collapse/expand by keyboard sends the user back to the top of the tab order.
- **Suggested Fix**: Keep one toggle element across both states (or focus the counterpart toggle in an effect); on queue collapse, focus the Toggle-queue button.

### A11Y-12: BufferingIndicator live region announces a new percentage on every chunk
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/BufferingIndicator.tsx:113-120,142-154`; `auralis-web/frontend/src/components/player/Player.tsx:106-112`
- **Status**: NEW
- **Description**: The indicator is always mounted in the Player and is `role="status" aria-live="polite"` (atomic by role). Its text content includes the percentage span (`47%`) and, while buffering, "Buffering...". `wsBufferedPercentage` changes with every processed chunk, so a screen reader reads the percentage (and status text) after each chunk for the whole stream, and "Buffering..." again on every seek. The `aria-label` it sets is not what live regions read on change.
- **Impact**: Repeated, unrelated "27%... 34%..." interruptions during playback; there is no way to silence them.
- **Suggested Fix**: Mark the percentage `aria-hidden`, keep the live region for the buffering/error transitions only, or expose the buffer as a `role="progressbar"` that is not live.

### A11Y-13: Player VolumeControl slider puts its changing value in `aria-label`, has no `aria-valuetext`
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/VolumeControl.tsx:100-105,190-203`
- **Status**: NEW
- **Description**: The native `<input type="range" min=0 max=1 step=.01>` is named `Volume control, 40%` (or `..., muted`). A name that embeds the live value is announced as a new accessible name on each change and duplicates the slider's own value announcement; the native value is `0.4` (0-1 scale) with no `aria-valuetext`, so the percentage can only come from the label. The Settings sliders (`PlaybackSettingsPanel.tsx:78-82,104-114`) use the right pattern (static `aria-label` + `getAriaValueText`). The mute button label embeds the keyboard glyph `(⌨ M )` and has no `aria-pressed`.
- **Suggested Fix**: Static label "Volume", `aria-valuetext={`${volumePercentage}%`}` (plus ", muted"), and put the shortcut in `aria-keyshortcuts` instead of the name.

### A11Y-14: White text on the semantic-red fill is 3.4-3.8:1 in both themes
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/design-system/primitives/Button.tsx:160-173` (danger); `auralis-web/frontend/src/components/player/QueuePanel/ClearQueueDialog.tsx:75-86`; `auralis-web/frontend/src/components/shared/ui/ConfirmationDialog.tsx:112-125`; `auralis-web/frontend/src/components/player/QueuePanel/styles.ts:136-140,150-154,253-257`; `auralis-web/frontend/src/design-system/primitives/Badge.tsx:56-75`
- **Status**: NEW (adjacent to #5675, which covers light-mode status text and aurora buttons, not white-on-red fills)
- **Description**: `themeVars.error` is `#EF4444` in both themes. White (`textPrimary` is 95% white) on it is 3.53:1; with `ConfirmationDialog`'s `opacity: .9` it is 3.61:1; danger-button hover/active opacity (0.9/0.8) gives 3.4-3.5:1. Normal-size (14-16px) labels need 4.5:1. Hit sites: Settings "Reset"/"Remove" (danger Button), "Clear" in `ClearQueueDialog`, the confirm button of `ConfirmationDialog` (Advanced settings), the queue `errorBanner` text, and the queue's hover-red "clear" button. `Badge` success/warning fills carry white at 2.54:1 and 2.15:1 (the primitive's consumers were not traced; #5132 says five primitives are unused).
- **Impact**: The labels of the app's destructive confirmations are low contrast, in dark mode too.
- **Suggested Fix**: Add a darker `danger` fill (e.g. `#DC2626`, 4.83:1 with white) used for any fill that carries text, as `errorHover` already exists in the token file.

### A11Y-15: Settings tabs have no tabpanel wiring; the album character pane is hover-only
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/settings/SettingsTabNav.tsx:51-58`; `auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx:42-100`; `auralis-web/frontend/src/components/shared/MediaCard/MediaCard.tsx:111-125,171-174`; `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:149-157`
- **Status**: NEW
- **Description**: (1) `StyledTabs` has no accessible name, the `Tab`s have no `id`/`aria-controls`, and the conditionally rendered panels (`activeTab === n`) have no `role="tabpanel"`/`aria-labelledby`. The sibling `ArtistDetailTabs.tsx:66-84` does it correctly. (2) In the Albums view the `AlbumCharacterPane` (energy meter, character tags, description) is populated from `onHoverEnter`/`onHoverLeave`, which `MediaCard` binds only to `onMouseEnter`/`onMouseLeave`; there is no `onFocus`/`onBlur` path, so keyboard and touch users never see it (WCAG 2.1.1, 1.4.13).
- **Siblings**: `ArtistDetailTabs` is the correct pattern for (1).
- **Suggested Fix**: Mirror `ArtistDetailTabs` in the settings tabs; call the hover callbacks from `onFocus`/`onBlur` on the stretched open button.

### TEST-03: TextDisabledContrast allowlist is keyed to `theme/themeConfig.ts`; the #5841 split moved the usage to `themePalette.ts` and the guard fails
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/__tests__/TextDisabledContrast.test.ts:112` (allowlist entry) and `:131-157` (scan); `auralis-web/frontend/src/theme/themePalette.ts:40`
- **Status**: NEW (a casualty of #5841; `theme/__tests__/darkOnlyTokenLeak.test.ts:41-48` was updated for the same split, this sibling was missed)
- **Description**: The guard greps every non-test module for `text.disabled` / `textDisabled` and fails on any file not in `ALLOWED_DISABLED_USAGES` (matched with `rel.endsWith(key)`). 6c4c5573 split `themeConfig.ts` into `themePalette.ts` / `themeTypography.ts` / `themeComponents.ts`; the MUI `text.disabled` slot now lives in `themePalette.ts:40` (`disabled: semantic.textDisabled`). The `'theme/themeConfig.ts'` entry is now dead and `themePalette.ts` is reported as an offender. Fails locally and in CI.
- **Evidence**:
  ```
  AssertionError: expected [ 'theme/themePalette.ts' ] to deeply equal []   (TextDisabledContrast.test.ts:155)
  ```
- **Impact**: One more red spec in a gate that is already red. The guard is a source-text scan keyed to file names, so every future split of a listed file breaks it the same way.
- **Siblings**: `styles/globalStyles.ts` is also on the allowlist; it still contains the usage after the keyframe/utility split, so it is fine today.
- **Related**: TEST-01, #5642 (source-text specs).
- **Suggested Fix**: Replace the `theme/themeConfig.ts` key with `theme/themePalette.ts`. Optionally key the allowlist on the module that defines the slot rather than on a path that a refactor can move.

### TEST-04: Baseline hides test-side drift: 11 time-format entries assert pre-#5787 output, and a one-argument `fetch` assertion went red unbaselined for CozyAlbumGrid
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/test-baseline.json:9-11` (useTrackFormatting), `:70-74` (TimeDisplay), `:100-102` (usePlayerDisplay); `auralis-web/frontend/src/components/library/__tests__/CozyAlbumGrid.test.tsx:113-115`; `.../AlbumDetailView.test.tsx:596,614`; `.../CozyArtistList.test.tsx`
- **Status**: NEW (the only dangling-mock cause, LibraryEmptyState, is #5678; these causes are different)
- **Description**: Two stale-expectation families were verified by running the specs.
  - (a) Time format. `utils/timeFormat.formatDuration` is now `H:MM:SS` from an hour up, `M:SS` below, and `'0:00:00'` for NaN/negative input. 11 baselined specs still expect other strings: `useTrackFormatting` expects `'61:01'` / `'60:00'` / `'150:45'`; `TimeDisplay` expects `'0:01:00 / 2:00:00'` and `'-0:58:59'` (zero-padded hour) and a `title` attribute (removed in #2556); `usePlayerDisplay` expects `'0:00'` for NaN/negative and `'0:30:00 / 2:00:00'`. #5822 hand-removed the flag-related siblings but left these. The `'0:00:00'` result for invalid input also puts a mixed-format `0:00:00 / 1:40` in the player when `currentTime` is NaN or negative on a short track, which the stale tests would have flagged had they been repaired.
  - (b) `#5519` (2026-10-18) moved `useInfiniteAlbums` onto the shared transport, so `global.fetch` is now called as `(url, {method, headers, signal, body})`. Specs asserting `toHaveBeenCalledWith(expect.stringContaining('/api/albums'))` (one argument) fail: `CozyAlbumGrid ... should fetch albums on mount` is not baselined (new CI failure); the same shape is baselined for `CozyArtistList` (2 tests) and `AlbumDetailView` (`'/api/albums/1/tracks'`, :596/:614).
  Other baselined families were also confirmed as test-side drift (not product bugs): TrackRow.test.tsx (12; queries `role="row"` and `data-testid="track-artwork"`, the row is `role="option"`), BatchActionsToolbar (9; role/title queries), VolumeScale (7; preloaded player state has no `streaming`, `selectEnhancedStreaming` throws), ConnectionStatusIndicator (10; component reads Redux, test drives WebSocketContext — the component itself is rendered nowhere in `src/`; see #5615).
- **Evidence**:
  ```
  useTrackFormatting.test.ts:48  expected '1:01:01' to be '61:01'
  usePlayerDisplay.test.ts:477   expected '0:00:00' to be '0:00'
  CozyAlbumGrid.test.tsx:113     expected "vi.fn()" to be called with arguments: [ StringContaining "/api/albums" ]  (actual: ["/api/albums?offset=0&limit=50", {method:'GET', headers, signal, body}])
  ```
- **Impact**: At least 60 of the 96 baselined failures are stale expectations, not known product defects. A baseline of this size makes the ratchet permissive (a real regression in `TrackRow` selection, `AlbumDetailView` click-to-play or the connection indicator cannot be told apart from the standing failures) and turns "known failure" into "never repaired".
- **Siblings**: see list above.
- **Related**: #5678, #5811 (phantom entries), #5822, #5615, #5679.
- **Suggested Fix**: Fix or delete the stale specs instead of baselining them: update the time-format expectations to the single `formatDuration` contract (and decide whether invalid input should render `0:00` or `0:00:00`), assert `fetch` with `(expect.stringContaining(...), expect.anything())`, then regenerate the baseline.

### TEST-05: `useEnhancementControl` "toggling ON re-issues…" waits on a value equal to the initial state, so it races its own fetch (flaky in CI)
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/__tests__/useEnhancementControl.test.ts:885-902`
- **Status**: NEW
- **Description**: The spec mocks `get` to resolve `{enabled: false, preset: 'adaptive', intensity: 0.6}`, then does `await waitFor(() => expect(result.current.enabled).toBe(false))`. `INITIAL_STATE.enabled` is already `false` (`hooks/enhancement/enhancementState.ts`), so `waitFor` returns on the first poll, possibly before the fetched intensity 0.6 has been applied. `setEnabled(true)` then re-issues with the default intensity 1.0 and the `{preset:'adaptive', intensity:0.6}` assertion fails. It passed in 3/3 isolated local runs but failed in a 3-directory batch run, and it appears as a new failure in 2 of the 4 sampled CI runs (39072771252, 39848359260).
- **Evidence**:
  ```ts
  get: vi.fn().mockResolvedValue({ enabled: false, preset: 'adaptive', intensity: 0.6 }),
  ...
  await waitFor(() => expect(result.current.enabled).toBe(false));   // already false before the fetch lands
  await act(async () => { await result.current.setEnabled(true); });
  expect(reissue).toHaveBeenCalledWith('play_enhanced', { preset: 'adaptive', intensity: 0.6 });
  ```
- **Impact**: Intermittent red CI on a spec that pins stream re-issue on toggle (#3759/#3763); with a ratchet gate, a flaky test is the hardest kind to baseline.
- **Siblings**: `:931` waits on the same `enabled === false` but only to assert a negative, so it cannot flake into a false failure (it can pass vacuously).
- **Related**: TEST-01.
- **Suggested Fix**: Wait on the loaded value, e.g. `await waitFor(() => expect(result.current.intensity).toBe(0.6))`.

### TEST-06: Lifecycle contracts left unpinned by the splits: `useStreamStartWatchdog` unmount cleanup and `usePlaybackTransport`'s resume-position registration
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useStreamStartWatchdog.ts:62-64`; `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:161-178`; `auralis-web/frontend/src/hooks/enhancement/__tests__/useStreamSubscriptions.test.tsx:10-13,109`; `auralis-web/frontend/src/test/setup.ts:39`
- **Status**: NEW (partially adjacent to #5683, which lists the stream-start hooks generally)
- **Description**: #5621 moved `clearStreamStartWatchdog()` out of the subscription cleanup, and the new spec explicitly delegates it: "unmount coverage belongs to useStreamStartWatchdog itself" (`useStreamSubscriptions.test.tsx:12,109`). No spec honours that: `useStreamStartWatchdog` has no direct spec, and `useAudioStreamingCore.watchdog.test.tsx` has three tests (fires, disarmed by message, re-arm) and none unmounts with a timer armed. A regression in `useEffect(() => clear, [clear])` would let the 45 s timer fire `cleanupStreaming` against a torn-down stream. Likewise `usePlaybackTransport`'s effect registering/unregistering the WS resume-position getters (the #3185 reconnect-resume path, dependency narrowed in #5621) and its disconnect effect are asserted nowhere: every spec only passes `setResumePositionGetter: vi.fn()`. The global WebSocketContext mock in `setup.ts:39` creates a fresh `vi.fn()` for `setResumePositionGetter` on every `useWebSocketContext()` call, whereas the real value is memoised (`useOutgoingChannel.ts:59-62`), so the identity-stability fix cannot be pinned through the global mock.
- **Evidence**:
  ```ts
  // useStreamSubscriptions.test.tsx:109
  // Unmount coverage is useStreamStartWatchdog's job, not this effect's.
  // useStreamStartWatchdog.ts:64
  useEffect(() => clear, [clear]);          // no spec unmounts with the timer armed
  ```
- **Impact**: A leaked stream-start timer or a missing resume-position registration would reach production with no failing test. Low, because each is a one-line effect and the surrounding paths are otherwise well covered.
- **Siblings**: other split hooks with no direct spec but reached through consumers (acceptable): `useEnhancementCommands`, `useStreamMessageHandlers`, `useOutgoingChannel`, `playerStateSnapshot`, `libraryPageFetch`, `queueMutationGuards`, `bufferHealth`, `WorkletOutput` (all exercised through `useEnhancementControl`, `useAudioStreamingCore.*`, `useWebSocketConnection.*`, `usePlayerStateSync`, `useLibraryPagination`, `useQueueMutations.*`, `BufferScheduler`/`AudioPlaybackEngine` specs).
- **Related**: #5683, #5621 (closed).
- **Suggested Fix**: Add a `useStreamStartWatchdog.test.ts` (arm, unmount, advance timers past the deadline, assert `onTimeout` not called) and a `usePlaybackTransport` spec asserting `setResumePositionGetter(sendType, fn)` on mount and `(sendType, null)` on unmount; make the global mock's `setResumePositionGetter` / `reissueActiveStreamAs` stable references hoisted next to `mockSubscribe`.

### TEST-07: The app-level navigation and global shortcut handlers in `useAppShortcuts` have no spec
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:132-206`; specs `src/__tests__/ComfortableApp.test.tsx` (playback keys only), `src/__tests__/ComfortableApp.errorBoundaries.test.tsx:76` (Ctrl+, only)
- **Status**: NEW
- **Description**: The shortcut table was extracted verbatim from `ComfortableApp` (#5631). `ComfortableApp.test.tsx` covers Space, ArrowRight/Left/Up/Down, `m` and the #5008 dropped-command toast, and the error-boundary spec presses Ctrl+, once. Nothing exercises `1`/`2`/`3` (view switch plus toast), `/` (focus and select `input[data-search-input]`), `Escape` (clear search first, otherwise close settings), or `?` (open help). `useKeyboardShortcuts*.test.ts` test the dispatcher generically, not these handlers.
- **Evidence**:
  ```ts
  // useAppShortcuts.ts:176-187  Escape: if (searchQuery) { setSearchQuery(''); info('Search cleared'); } else if (settingsOpen) { setSettingsOpen(false); }
  ```
  `grep -rn "Search cleared\|Songs view" --include=*.test.*` finds only `AppViewAnnouncement.test.tsx`, which does not go through the shortcut.
- **Impact**: A regression in Escape precedence or the `/` selector (the `data-search-input` contract from #5662) would ship unnoticed.
- **Siblings**: none.
- **Related**: #5632 (advertised-vs-real shortcut lockstep; pinned in `Player.test.tsx:279`).
- **Suggested Fix**: Add `useAppShortcuts.test.ts` that renders the hook with stubs and invokes each handler.

## Relationships

- **Engine pointer vs local playback (RDX-01, RDX-02, RDX-03, RDX-04, HK-01, HK-11; open #5460, #5726).** Next/Previous are Redux-only by design (#5601), so the backend engine pointer lags the track that is actually playing. Each finding is a different path where that lag leaks back into the playing track's Redux state:
  - snapshot `duration` (RDX-02);
  - the initial queue fetch (RDX-03);
  - `removeTrack` index arithmetic (RDX-04);
  - the `isPlaying` flag (RDX-01).

  HK-01 corrupts the local clock itself. All of them converge on `useAutoAdvance` and `isPlaybackActive`, which is why the symptoms are skipped or stalled advances. The fix should be designed once: either a single local "playing track + position" authority that snapshots cannot overwrite unless the track ids match, or making the engine pointer authoritative (#5460).
- **Stream-session identity (RDX-05, HK-04, HK-10, HK-09).** No single identity token survives end, error, reissue and reconnect.
  - `stream_epoch` gates chunks but not end or error frames (RDX-05).
  - `lastStreamCommand` outlives the session it describes (HK-04), and replays a stale `start_position` (HK-10).
  - The engine's async start has no cancellation token (HK-09).

  One per-session token checked at every side-effect boundary would close all four.
- **Connection lifecycle (HK-03, A11Y-02; open #5615).** The WebSocket gives up after its retry budget. The only reconnect affordance, `ConnectionStatusIndicator`, is orphaned (#5628), and the mounted dot has no text. A user whose backend restarts slowly is left with a dead app and only a red dot.
- **Render churn (HK-02, PERF-04, PERF-03).** The playback context value changes every tick (HK-02) and ComfortableApp subscribes to volume (PERF-04). Both re-render the app shell at high frequency. PERF-03 is the remaining unvirtualized list.
- **Library data freshness (API-01, PERF-02, CMP-03, CMP-04, CMP-06, CMP-07).** Two data layers coexist: React Query for albums and fingerprints, hand-rolled pagination for tracks and artists.
  - Invalidation reaches only the hand-rolled layer (API-01).
  - Refresh in that layer costs O(pages loaded) (PERF-02).
  - Search and sort are applied client-side over partial pages (CMP-03, CMP-04).
  - Error states discard loaded data or masquerade as empty (CMP-06, CMP-07).
- **Light-mode semantics (DS-01, DS-02, DS-05, A11Y-08, A11Y-14; open #5675).** These all come from roles that were tuned for dark mode only. A role-contrast test in `semanticTheme.roles.test.ts`, covering surfaceRaised vs surfacePrimary, badge fill vs ink, and danger fill vs white, would pin the whole group.
- **Test gate (TEST-01, TEST-02, TEST-03, TEST-04, TEST-05; open #5679, #5678).** TEST-02 through TEST-05 are each part of why the gate is red or permissive. Fix TEST-01's environment drift first, then regenerate the baseline from a CI artifact. Otherwise each individual fix is invisible.
- **Orphaned code inflating the surface (#5628 open).** One finding was dropped at merge because the code it targeted is never mounted: API-02, global-search request races in `useSearchLogic`, which only the orphaned `GlobalSearch` uses. DS-04's hex-suffix sites and part of A11Y-02 also sit in orphaned files. Deciding mount-or-delete for #5628 shrinks several findings at once.

## Prioritized Fix Order

1. **HK-01**: a one-line `setSeekOffset` in the seek path, plus a spec. HIGH, user-visible on every seek, and it breaks auto-advance.
2. **TEST-01, then TEST-02 and TEST-03.**
   - Shim or disable FocusTrap restore under jsdom 30, or pin jsdom.
   - Fix the `usePlaybackQueue` spec store and the `themePalette` allowlist key.
   - Regenerate the baseline from a CI artifact.

   Every later fix needs a working ratchet to be verifiable.
3. **CMP-01**: route `playlist-N` to a playlist view, or stop navigating there. Also fix the `playlist--1` delete path.
4. **RDX-04, RDX-02, RDX-03**: small reducer and gate changes that stop wrong-track advances. Do them together with the RDX-01 writer fix.
5. **HK-04 and RDX-05**: clear `lastStreamCommand` on session end, and gate end/error side effects on the track id or epoch. These prevent unprompted replays and teardown of the new track.
6. **HK-02**: stabilise `onCleanupExtra` and `onDisconnectExtra`. Cheap, and it restores the #5006 guarantee.
7. **HK-03 + A11Y-02**: re-arm on `online`/`visibilitychange` and give the status indicator text and a live region.
8. **CMP-02, CMP-06, CMP-07, API-01, CMP-03, CMP-04**: library correctness and freshness.
9. **DS-02, DS-01, DS-03**: light-mode surface step, badge, and keyframe-name collisions. Add the role-contrast test.
10. **A11Y-01, A11Y-03 through A11Y-08**: keyboard and focus paths, starting with the context-menu event bubbling (A11Y-01).
11. **The remaining MEDIUM findings**, then **LOW findings opportunistically**. Dead-code deletions (HK-12, RDX-08, DS-11, TS-04) are best batched with #5628.

## Existing (skipped)

Open issues re-encountered and confirmed still present. They are not counted above.

- **Components**:
  - #5614, #5617: context-menu items do nothing, and playlists are never loaded.
  - #5628: 33 orphaned component files. New members seen this run: `ConnectionStatusIndicator` (A11Y-02/HK-03), `GlobalSearch`/`useSearchLogic` (dropped API-02), `LibrarySearchControls` (DS-04).
  - #5630: callbacks drilled through 3 components.
  - #5634: deferred callbacks. The `useProgressiveImageLoader` retry timeout remains, see also #5353.
  - #5647: failed favourite toggle. The fix `db9cc2e7` is in the tree; the issue is still open, so it can be closed.
- **Redux / state**:
  - #5615: `connection` slice is write-dead.
  - #5616: `player.streaming.normal` is never written.
  - #5460: queue edits do not update `PlayerStateManager`.
  - #5726: `current_track` goes stale after a queue-driven advance.
  - #5129, #5016: dead selectors.
  - #5651: bulk add-to-queue. The fix `e9a8f42c` is in the tree; the issue is still open, so it can be closed.
- **Hooks / API**:
  - #5636: un-discriminated WS handler union.
  - #5649, #5190: raw `fetch()` sites without a timeout.
  - #5650: cancellation gaps.
  - #5652: error-message normalisation.
  - #5653: the documented abort contract.
  - #5654: the WS URL ignores `VITE_API_URL`.
  - #5655: initial-state fetches swallow failures.
  - #5823: twin wire spellings.
- **Types**:
  - #5377: `any` in two files.
  - #5131: response types omit backend fields.
- **Design system**:
  - #5648: literal spacing, radius and typography values; still large, about 590 `Npx` literals.
  - #5675: light-mode WCAG for accent and status colours.
  - #5132: unused primitives.
  - #5646: dead palette. The fix `3d4a152c` is in the tree; the issue is still open, so it can be closed.
  - #5644: doubled `px`. No live instance was found, so it looks fixed.
- **Accessibility**:
  - #5669: every toast is `role=alert`.
  - #5671: heading levels.
  - #5672: virtualized lists expose no set size or position.
  - #5676: reduced motion, and the inert visualizations toggle.
  - #5633: recently-touched albums.
  - #5134: Modal close button has no name.
- **Tests**:
  - #5673: may be largely satisfied by the transport specs added since; re-triage.
  - #5674, #5677: vacuous assertions.
  - #5678: dead `vi.mock` targets. New sibling: `components/library/Items/tracks/__tests__/TrackRow.artworkCacheBust.test.tsx:17`.
  - #5679, #5680, #5681, #5682.
  - #5683: `useSettingsDialog.test.ts` and `usePlaylistData.test.ts` now exist.

### Triage notes (open issues that look stale)

- **#5128** (three ErrorBoundary implementations): only `components/core/ErrorBoundary.tsx` exists. Candidate to close.
- **#5130** (`useQueueHistory` `isMountedRef`): the hook no longer exists. Candidate to close.
- **#5646, #5647, #5651**: the fix commits are in the tree. Verify and close.
- **#5644**: no live `${token}px` instance remains. Verify and close.
