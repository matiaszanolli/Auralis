# Frontend Audit Report - 2026-11-17

**Scope**: `auralis-web/frontend/src/` (components, hooks, contexts, store, services, types, design system, tests). Full audit, depth deep, all 9 dimensions, fresh read of current code at HEAD (7029fa50a). Dedup baseline: 6090 GitHub issues (highest #6346), verified untruncated. `test-baseline.json` is empty, so no failing spec was reported.

## Executive Summary

| Severity | New / Regression | Existing (already tracked) |
|----------|------------------|----------------------------|
| CRITICAL | 0 | 0 |
| HIGH | 0 | 0 |
| MEDIUM | 13 | 0 |
| LOW | 44 | 4 |
| **Total** | **57** | **4** |

Of the 57 reportable findings, 8 are regressions of closed issues (D5-01, D6-02, D8-01, D8-02, D1-01, D5-02, D5-03, D8-07). Five cross-dimension duplicates were merged (D3-01 into D2-01, D3-03 into D6-02, D8-03 into D5-01, D4-05 into D6-06, D3-09 into D2-07); the dimension agents' raw count was 66 before merging.

No CRITICAL or HIGH findings. Production type safety is clean (no `any`, no `@ts-ignore`, `tsc -p tsconfig.build.json` 0 errors, WebSocket message types match the backend field for field).

### Key themes

1. **Queue index reconciliation is incomplete (D2-01, D2-02, D2-05).** The sidebar's `PlaylistList` mounts a second `usePlaybackQueue()` through `usePlaylistContextActions`; collapsing or expanding the sidebar remounts it, re-fetches the queue and writes the engine's raw, stale `current_index` without the #5601 reconciliation. Next can then play the wrong track or replay the current one. This is the highest-impact user-visible bug in the report.
2. **Closed accessibility/contrast and cancellation issues have regrown (D5-01, D5-02, D8-01, D8-02, D8-07, D6-02).** #5675 (light-mode contrast), #6026 (focus on detail-view back), #5672 (virtualized list size/position) and #5650 (query cancellation, via #5519) were closed but the fix does not cover every site. Several were closed on the same day as this audit or shortly before; they should be reopened or re-filed with the full sibling list.
3. **Request lifecycle hygiene in hooks (D6-01, D6-02, D6-03, D3-02).** `retryTransient` never retries the plain-object errors `useRestAPI` throws, so the initial-state retry is inert in production; `useInfiniteAlbums` ignores the query `AbortSignal`; `useSearchLogic` has stale-response, early-loading-clear and unshown-error defects; `useLibraryQuery.refresh()` can leave `isFetchingRef` stuck.
4. **Keyboard and screen reader behaviour (D8-04, D8-05, D8-06).** Each track row adds extra Tab stops inside a `role="option"` listbox, Escape in the Reset Library confirmation also closes Settings, and single-character shortcuts cannot be disabled (WCAG 2.1.4).
5. **Performance outliers (D7-01, D7-02).** Playlist detail is unvirtualized, and the AlbumCharacterPane decay animation re-renders at 60 Hz and mints unbounded Emotion classes.
6. **Residual dead code and file-size drift (D1-01, D1-02, D1-07, D2-03, D2-04, D5-03, D5-04, D9-05).** `CozyLibraryView.tsx` regrew to 335 lines and the LOC ratchet froze the overshoot; #6275 was closed with its 120-line function bar unmet for 7 of its 10 hooks; about 33 orphaned components (#5628) and 2,300 lines of specs still pin unmounted code.

### Most impactful issues

D2-01 (wrong track plays after sidebar toggle), D6-01 (inert retry), D6-03 (search dropdown races), D3-02 (library pagination stuck), D8-04/D8-05 (keyboard traps), D7-02 (60 Hz re-render).

## Findings

## CRITICAL (0)

None.


## HIGH (0)

None.


## MEDIUM (13)

### D2-01: Re-mounting any `usePlaybackQueue()` consumer re-fetches the queue and writes the engine's raw (stale) index, undoing the #5601 reconciliation
- **Severity**: MEDIUM
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:187-188`, `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:169-172`, `auralis-web/frontend/src/components/playlist/usePlaylistContextActions.ts:28`, `auralis-web/frontend/src/components/layouts/Sidebar/Sidebar.tsx:49-60`
- **Status**: NEW (missed sibling of closed #5601; root cause is open #5937, which this does not duplicate)
- **Description**: #5601 made `player_state` snapshots (`playerStateSnapshot.ts:122`) and `queue_changed` (`useQueueSubscription.ts:70`) run the engine's `queue_index` through `reconcileQueueIndex`, because navigation is client-authoritative and the engine pointer lags (`GET /api/player/queue` returns `queue_obj.get_queue_info()['current_index']`, i.e. the engine pointer, `services/queue_service.py:62-76`). `useQueueFetch` is a third writer of `queue.currentIndex` and it was not converted: it dispatches `setCurrentIndex(response.current_index ?? 0)` raw. `useQueueFetch` is not an app-singleton: it runs inside `usePlaybackQueue()`, which has two production callers, `QueuePanel` (always mounted in Player) and `usePlaylistContextActions`, called unconditionally from `PlaylistList` in `SidebarContent`. `Sidebar` swaps its whole subtree for `CollapsedSidebar` when `collapsed` is true, so every collapse/expand of the sidebar (and a desktop<->mobile breakpoint swap in `AppSidebar`) unmounts and re-mounts `PlaylistList` -> `usePlaybackQueue` -> a fresh `useQueueFetch` -> a new GET.
- **Evidence**:
  ```ts
  // useQueueFetch.ts:187-188  (no reconcileQueueIndex, no playing-track check)
  dispatch(reduxSetQueue((response.tracks ?? []).map(mapTrackInfoToTrack)));
  dispatch(reduxSetCurrentIndex(response.current_index ?? 0));
  // usePlaylistContextActions.ts:28
  const { setQueue } = usePlaybackQueue();   // only needs the setQueue mutation, but mounts fetch + WS subscription
  // Sidebar.tsx:49
  if (collapsed) { return <CollapsedSidebar onToggleCollapse={handleToggle} />; }
  ```
  `usePlaybackNavigation.step` computes the target as `currentQueueIndex + delta` from Redux (`usePlaybackNavigation.ts:47`).
- **Impact**: Queue [A,B,C,D], user plays A, presses Next twice (playing C, Redux index 2, engine pointer still 0). User collapses then expands the sidebar: the GET returns `current_index: 0`, Redux index becomes 0 while `player.currentTrack` is still C. The queue highlight jumps to A and the next Next/auto-advance plays B instead of D. It heals only when the next `player_state`/`queue_changed` snapshot (which does reconcile) arrives. The same unconditional double mount also means at startup there are two REST fetches and two `queue_changed` subscriptions, so every `queue_changed` maps the whole queue (up to 50 000 tracks) and dispatches `setQueue` twice. The fetch also has no ordering guard against a WS frame that lands while the GET (plus `retryTransient` back-off) is outstanding, so an older GET body can overwrite a newer `queue_changed`.
- **Suggested Fix**: Make the initial fetch and the WS subscription app-singletons (call `useQueueFetch()`/`useQueueSubscription()` once, e.g. next to `usePlayerStateSync()` in `App.tsx`) and have `usePlaybackQueue()` and `usePlaylistContextActions` read Redux / `useQueueMutations()` only. In `useQueueFetch` run the index through `reconcileQueueIndex(tracks, response.current_index, store.getState().player.currentTrack?.id)` (read via `useStore`, as `playerStateSnapshot` does) and skip the dispatch if a WS frame has already populated the queue.
- **Cross-dimension note**: Also found by Dimension 3 as D3-01 (same root cause: `usePlaylistContextActions` mounts a second `usePlaybackQueue()`).

### D3-02: useLibraryQuery.refresh() supersedes an in-flight executeQuery and leaves `isFetchingRef`/`isLoading` stuck, disabling fetchMore and same-key refetch
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQueryFetchers.ts:75-132` (cleanup), `:190-201` (refresh), `:135-137` (fetchMore gate); trigger in `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:62-67`
- **Status**: NEW
- **Description**: `executeQuery` clears `isFetchingRef` and `setIsLoading(false)` only `if (!isStale())`. `refresh()` (called on every `library_updated`/`metadata_*`/`library_tracks_removed` frame by CozyArtistList) takes a new id via `beginRequest()` and aborts the prior request via `claimRequest()` whenever `dataLengthRef.current > 0`, but unlike `executeQuery` it never resets `isFetchingRef` or `isLoading`. If an `executeQuery` is in flight when `refresh()` runs (data > 0 because a search/sort change keeps the previous rows while the new page loads, and during a scan broadcasts are frequent), the executeQuery is aborted, becomes stale, and skips its cleanup; the refresh then completes without clearing the flags.
- **Evidence**:
```ts
// executeQuery
      } finally {
        if (!isStale()) {            // superseded by refresh() => skipped
          isFetchingRef.current = false;
          setIsLoading(false);
        }
      }
// refresh: new id + abort, but no flag cleanup
    const result = await fetchLoadedPages({ ..., isStale: beginRequest(), signal: claimRequest() });
    if (result.kind !== 'refreshed') return;
    setData(result.items); ...                 // isFetchingRef / isLoading untouched
// fetchMore
    if (isFetchingMoreRef.current || !hasMore || isFetchingRef.current) return;
```
- **Impact**: After the race, `isLoading` stays true and `isFetchingRef` stays true. `fetchMore` returns immediately forever (infinite scroll in the artist list stops at the first page), and `refetch()`/the auto-fetch effect for the same query key hit the `queryKeyRef === queryKey && isFetchingRef.current` early return. It only recovers when the user changes the search/sort to a new key. Scoped to `useLibraryQuery`; `useLibraryPagination` is safe (its refresh path clears data first, and its `loadMore`/`fetchTracks` settle independently).
- **Suggested Fix**: Have `refresh()` own the shared flags when it supersedes (clear `isFetchingRef`/`setIsLoading(false)` in its own `finally` when still newest), or track in-flight per request id so a superseded request that was superseded by a non-`executeQuery` path still releases the flag.

### D5-01: Dark-palette `semantic.*` status colours used as text on themed (light-capable) surfaces
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/shared/ContextMenu/ContextMenu.styles.ts:31,54`; `components/shared/ui/ConfirmationDialog.tsx:52,65`; `components/shared/CacheStatsDashboard.tsx:60`; `components/shared/CacheStatsDashboard/StatCards.tsx:18-23,44-50`; `components/shared/SimilarTracksModal/SimilarTracksModal.tsx:158-162`
- **Status**: Regression of #5675 (closed; its CONSISTENCY check "every `tokens.colors.semantic.(success|warning|error)` used as text colour" was only applied to the Settings cards)
- **Description**: `themeVars.success/warning/error/info` is the theme-aware source: in light mode it resolves to `lightMode.accent.*` (darkened, >=4.5:1 on `#F8F9FD`/`#FFFFFF`, see the comment at `design-system/tokens/colors.ts:226-227`). Several live components still read the raw dark-mode hexes `tokens.colors.semantic.*` for TEXT painted on `themeVars.*` surfaces, so in light mode they fall below WCAG AA. The `darkOnlyTokenLeak.test.ts` guard only forbids `tokens.colors.text|bg.*` and white-alpha fills, so `semantic.*` slipped through.
  Computed contrast on white (light `surfacePrimary`/`menuSurface`): `#EF4444` error 3.76:1, `#10B981` success 2.54:1, `#F59E0B` warning 2.15:1, `#3B82F6` info 3.68:1 (AA needs 4.5:1 for these 13-18px labels).
  Live sites (all text): context-menu destructive item label (ContextMenu.styles.ts:31; icon at :54), confirmation-dialog danger title (ConfirmationDialog.tsx:65, border :52), cache-stats load-error message (CacheStatsDashboard.tsx:60), PercentageDisplay numeral (StatCards.tsx:18-23, `color,` at ~:50; reached from CacheStatsDashboard in Advanced Settings), similar-tracks error/transient title (SimilarTracksModal.tsx:158-162).
  Same pattern in orphaned components (not counted; see #5628): `ConnectionDetailsPanel.tsx:112-113,157-158,196-199,221`, `ProcessingStatsChips.tsx:42-46`, `ConnectionStatusIndicator.tsx:92-95`.
- **Evidence**:
```ts
// ContextMenu.styles.ts:31  (surface is themeVars.surfaceSecondary / menuSurface)
color: destructive ? tokens.colors.semantic.error : themeVars.textPrimary,
// ConfirmationDialog.tsx:62-65  (dialog bg: themeVars.surfacePrimary)
color: isDangerous ? tokens.colors.semantic.error : themeVars.textPrimary,
// StatCards.tsx:18-23
? tokens.colors.semantic.success : ... tokens.colors.semantic.warning : tokens.colors.semantic.error;
```
- **Impact**: With the shipped light theme, the destructive menu item, the danger confirmation title, cache-stat percentages (success/warning at 2.5/2.2:1) and error messages are low-contrast. The theme contract (`themeVars` is the only theme-aware colour source) is bypassed.
- **Suggested Fix**: Use `themeVars.error/success/warning/info` for text and icon colours at these sites (keep `tokens.colors.semantic.*` only where the colour is a dark-surface fill or non-text border). Extend `darkOnlyTokenLeak.test.ts` with a `tokens\.colors\.semantic\.(success|warning|error|info)` rule and an allowlist for the non-text uses (borders/fills/dots), so new sites cannot reappear.
- **Cross-dimension note**: Also found by Dimension 8 as D8-03 (same sites: ContextMenu.styles.ts, ConfirmationDialog.tsx, Alert primitive; the accessibility view of the same defect).

### D6-01: retryTransient never retries errors from useRestAPI (initial-state retry is inert in production)
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `utils/retryTransient.ts:30`, `hooks/api/useRestAPI.ts:181-188`, callers `hooks/player/useQueueFetch.ts:49`, `hooks/enhancement/useEnhancementStatusSync.ts:111`
- **Status**: NEW (follow-up to the retry added for open #5655; the retry does not work for these two call sites)
- **Description**: `retryTransient` rethrows anything that is not an `Error` instance: `!(error instanceof Error) || !isRetryableError(error)`. Both callers pass the getter from `useRestAPI()`. That hook's catch block converts every failure into `ApiErrorHandler.parse(err)` and does `throw apiError`. `parse()` returns a plain object literal, `{ status, message }`, which is not an `Error`. So a real backend failure never reaches the retry rule. A backend that is still starting (TypeError "Failed to fetch", or a 502/503) is rethrown on the first attempt. The #5655 scenario is "the backend is often still coming up when the window opens", and it still leaves the queue and enhancement settings at their defaults until reload. The unit tests pass because they feed `APIRequestError` instances (`utils/__tests__/retryTransient.test.ts`, `hooks/player/__tests__/useQueueFetch.retry.5655.test.ts:33`). The real `useRestAPI` never throws that class.
- **Evidence**:
```ts
// retryTransient.ts:30
if (delay === undefined || isCancelled() || !(error instanceof Error) || !isRetryableError(error)) { throw error; }
// useRestAPI.ts:186-188
const apiError = ApiErrorHandler.parse(err);   // plain { status, message }
setError(apiError);
throw apiError;
```
- **Impact**: The "three attempts, ~1.3 s patience" start-up resilience is dead code for the two paths it was written for. A related effect is that `useRestAPI` maps a fetch-level network failure to `status: 500` instead of 0, because it never goes through `apiRequest`'s status-0 wrapping. Code that reads `ApiError.status` therefore cannot tell "backend unreachable" from "server error". The same applies to a 200 response that fails `validate`, which becomes 500 rather than `apiRequest`'s non-retryable 200.
- **Suggested Fix**: Make `retryTransient` and `isRetryableError` accept the `ApiError` shape: use `isApiError(error)` and pass `error.status` to `isRetryableStatus`. Alternatively, have `useRestAPI` throw an `Error` subclass that carries `status` (the `HttpStatusError` branch in `queryRetry.ts` already handles that). Add a test that drives the real `useRestAPI` against a failing `fetch`.

### D6-02: useInfiniteAlbums queryFn drops the query's AbortSignal (siblings: playlist fetches)
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/library/useInfiniteAlbums.ts:35-68,103-112`; siblings `components/playlist/usePlaylistData.ts:43`, `components/playlist/usePlaylistContextActions.ts:39`, `components/library/Items/tracks/useTrackContextMenu.ts:54`
- **Status**: Regression of #5650 (closed; its fix covered the fingerprint, stats and cache queryFns but not this one)
- **Description**: `queryFn: async ({ pageParam })` never destructures `signal`, and `fetchAlbums()` has no signal parameter, so `get()` is called without one. The comment above the call says "composes the 30s default timeout with the query's AbortSignal", which is false. `queryKey` includes `search`, so each keystroke in the album-grid search supersedes the previous query. React Query only cancels the HTTP request if the queryFn consumed the signal, so every superseded `/api/albums?...` runs to completion on the single-process backend. The same applies on unmount. Sibling gaps with no signal: `playlistService.getPlaylists()` in `usePlaylistData.refresh`, `getPlaylist` in `usePlaylistContextActions.onPlay`, and `getPlaylists()` in `useTrackContextMenu.fetchPlaylists`. `getPlaylists` can aggregate up to `MAX_PLAYLIST_PAGES` pages, and these callers only discard the result via a ref guard.
- **Evidence**:
```ts
queryFn: async ({ pageParam }) => {
  const apiResponse = await fetchAlbums({ pageParam, limit, search, orderBy, order });  // no signal
...
return get<AlbumsApiResponse>(`/api/albums?${params}`, { validate: isAlbumsListShape }); // no signal
```
- **Impact**: Typing in the album search issues overlapping full requests that cannot be cancelled. The checklist requires superseded or unmounted React Query queries to cancel their request.
- **Suggested Fix**: `queryFn: ({ pageParam, signal }) => fetchAlbums({ ..., signal })` and forward `signal` into `get()`. Pass the existing `AbortController` signal through `getPlaylists` in the sibling hooks.
- **Cross-dimension note**: Also found by Dimension 3 as D3-03 (Regression of #5650; #5650 deferred this to #5519, which closed without fixing it).

### D6-03: useSearchLogic: late response resurrects the dropdown, superseded request clears loading, failures invisible, no unmount abort
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `components/library/Hooks/useSearchLogic.ts:55-72,148-166,167-171`
- **Status**: NEW
- **Description**: Four related defects in one request path.
  1. The only abort is at the start of the next `performSearch`. Shortening the query below 2 characters (line 57-59), `handleClear` and `handleResultClick` set `showResults(false)` and clear `results` but do not abort the in-flight request. When it lands, `controller.signal.aborted` is false, so it runs `setResults(...)` and `setShowResults(true)`. The results panel reappears over an empty or cleared search box.
  2. `finally { setLoading(false) }` is unconditional. A superseded request (aborted, then returning early) clears `loading` while the newer request is still in flight. Other hooks guard this with `if (!controller.signal.aborted)`.
  3. The `catch` only does `console.error`. There is no error state, so on a 500 or timeout the user sees the previous query's results (or nothing) with no indication that the search failed.
  4. There is no cleanup abort on unmount. The effect cleanup only clears the debounce timer, so up to three requests run on after unmount.
- **Evidence**:
```ts
const timeoutId = setTimeout(() => { performSearch(query); }, SEARCH_DEBOUNCE_MS);
return () => clearTimeout(timeoutId);          // no abort
...
setResults([...tracks, ...albums, ...artists]);
setShowResults(true);                           // runs even if the user cleared the box
} catch (error) {
  if (controller.signal.aborted) return;
  console.error('Search error:', error);        // never surfaced
} finally { setLoading(false); }                // also for superseded requests
```
- **Impact**: Visible UI glitches: the dropdown pops back after clearing, the spinner disappears early, and failed searches look like "no change".
- **Suggested Fix**: Abort `abortControllerRef` whenever the query drops below 2 characters, in `handleClear`/`handleResultClick`, and in an unmount cleanup. Guard `finally` with `if (!controller.signal.aborted)`. Add an `error` field (using `failureMessage('Search failed', err)`).

### D7-01: PlaylistDetailView renders every playlist track in an unvirtualized table
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Details/PlaylistDetailView.tsx:185-190`, `auralis-web/frontend/src/components/library/Items/tables/AlbumTrackTable.tsx:52-65`, `auralis-web/frontend/src/components/library/Details/usePlaylistDetails.ts:1-12`
- **Status**: NEW (sibling of closed #6023 / #4471 / #3576; none covers the playlist detail view)
- **Description**: `usePlaylistDetails` fetches the playlist with *every* track eagerly loaded in a single request. The doc comment says so explicitly: "no pagination to drive". `PlaylistDetailView` hands the whole array to `AlbumTrackTable`, which does a plain `tracks.map(...)` into `TrackTableRowItem`. Each row is a `StyledTableRow` with four cells, three `Typography`, an `IconButton`, a `useTrackContextMenu` instance (4 `useState`, `useToast`, a `useMemo` for actions) and a mounted `ContextMenu` (two effects plus a `StyledMenu`). Every other large track surface is windowed: songs/favourites list, grid, queue, artist `TracksTab` (#6023) and the cache-stats list. `AlbumTrackTable` was written for album detail, where the row count is small, and playlist detail reuses it unchanged. Playlists have no size bound, and "add all" or drag-and-drop make multi-thousand-track playlists easy to build.
- **Evidence**:
```tsx
// PlaylistDetailView.tsx:185
<AlbumTrackTable tracks={tracks} onTrackClick={handleTrackClick} onFindSimilar={handleFindSimilar} formatDuration={formatDuration} />

// AlbumTrackTable.tsx:52-65
{tracks && tracks.length > 0 ? (
  tracks.map((track, index) => (
    <TrackTableRowItem key={track.id} track={track} index={index}
      isCurrentTrack={currentTrackId === track.id} isPlaying={isPlaying} ... />
```
  The same table sits in a `TableContainer` with `backdropFilter: 'blur(12px)'` (AlbumTrackTable.tsx:44) and `overflow: hidden`. With 1000+ rows that is one very tall backdrop-filtered layer.
- **Impact**: Opening a large playlist mounts one row per track (thousands of DOM nodes and component instances), so the open stalls the main thread. Every play, pause or track change re-runs the `.map` and the memo comparators for all rows. The tall backdrop-filter layer adds paint and GPU cost on scroll. Window scrolling and the playback transport share the same main thread.
- **Suggested Fix**: Window the rows the way `TracksTab` does (`useVirtualizer` against `#app-main-content-scroll`, spacer rows, a measured row height), or add a `virtualized` mode to `AlbumTrackTable` that `PlaylistDetailView` turns on. Keep the unwindowed path for jsdom, as the other tables do. Drop or scope the `backdropFilter` on the table container.

### D7-02: AlbumCharacterPane decay animation re-renders the whole pane at 60 Hz and mints thousands of unique Emotion classes per pause (#3954 fixed only the container)
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/usePlaybackWithDecay.ts:45-76`, `.../AlbumCharacterPane.tsx:208-260,275`, `.../GlowingArc.tsx:19-82`, `.../EnergyField.tsx:13-110`, `.../CharacterTags.tsx:23-75`, `.../FloatingParticles.tsx:12-45`, `.../WaveformVisualization.tsx:84`
- **Status**: NEW (the #3954 fix is still in place for `containerStyles` and for the Waveform `::before` glow, so this is not a regression. It is the unfixed rest of the same pattern.)
- **Description**: When playback stops or pauses, `usePlaybackWithDecay` runs a 2.5 s rAF loop that calls `setIntensity(newIntensity)` every frame. `decayStartTimeRef` is `performance.now()`, a non-quantized float, so each decay yields a different series of float values. `AlbumCharacterPane` re-renders on every frame. #3954 rounded `glowIntensity` to 2 dp for `containerStyles` and the Waveform `::before`, but the **raw** `intensity` is still passed to five children and used in the pane's own mood-prompt box:
  - `GlowingArc`: `withOpacity(VIOLET, 0.1 + glowIntensity*0.3)`, `filter: blur(${12 - glowIntensity*4}px)` and `opacity`, with glowIntensity taken from the raw intensity.
  - `EnergyField`: `opacity: 0.7 + intensity*0.3` on two captions, and `hsla(..., ${0.25 + intensity*0.15})` gradient stops.
  - `CharacterTags`: `color-mix(... ${((0.4 + glowIntensity*0.15)*100).toFixed(2)}%)` and `box-shadow` per chip.
  - `FloatingParticles`: wrapper `opacity: intensity`.
  - `WaveformVisualization` bars: `opacity: 0.7 + value*0.2 + intensity*0.1`, unrounded, for 7 bars. Only the `::before` uses the rounded value.
  - The pane's mood-prompt `Box`: `opacity: 0.7 + intensity * 0.2`.
  Each distinct `sx` serialization inserts a new CSS rule through Emotion, and Emotion never evicts rules. That is roughly 25-30 new rules per frame, so a few thousand per decay. Decays occur on every pause, stop and track change (the gap between tracks is a `playing -> stopped` transition until the next start cancels it). Every element also declares `transition: all ${tokens.transitions.slow}` on the very properties being rewritten each frame, so the CSS transition restarts every frame.
  Second sibling: `computeAlbumCharacter(displayFingerprint)` (AlbumCharacterPane.tsx:208) runs un-memoized on every render and returns fresh `tags` and `rotatingDescriptions` arrays. This defeats `React.memo` on `CharacterTags` (its `tags` prop is a new array each time), so even a render with unchanged intensity re-renders the chips.
- **Evidence**:
```ts
// usePlaybackWithDecay.ts:50-64
decayStartTimeRef.current = performance.now();
const animateDecay = (currentTime: number) => {
  ...
  const newIntensity = 1 - easedProgress;
  setIntensity(newIntensity);            // 60 Hz, un-rounded float
```
```tsx
// AlbumCharacterPane.tsx:208-252
const character = computeAlbumCharacter(displayFingerprint);   // not memoized -> new arrays
<FloatingParticles isAnimating={isAnimating} intensity={intensity} count={15} />
<WaveformVisualization ... intensity={intensity} />
<GlowingArc ... intensity={intensity} energyLevel={character.energyLevel} />
<CharacterTags tags={character.tags} isAnimating={isAnimating} intensity={intensity} />
<EnergyField energy={character.energyLevel} isAnimating={isAnimating} intensity={intensity} />
// :275  opacity: 0.7 + intensity * 0.2,
```
```tsx
// WaveformVisualization.tsx:32 vs :84 - rounded for the glow, raw for opacity
const glowIntensity = Math.round(Math.sqrt(intensity) * 100) / 100;
opacity: 0.7 + value * 0.2 + intensity * 0.1,
```
- **Impact**: On each pause or track change the main thread does about 150 full pane renders plus a few thousand Emotion rule insertions in 2.5 s. This coincides with the user's most latency-sensitive moments (pause, skip). The inserted rules accumulate for the whole session, so style recalculation slows down over a long listening session.
- **Suggested Fix**: Do not drive a purely visual fade through React state. Write the decaying value to a CSS custom property on the pane root via a ref (`style.setProperty('--pane-intensity', ...)`) and let the children use `calc()` over `var(--pane-intensity)`. Failing that, quantize `intensity` inside the hook (steps of 0.05) so the number of distinct values is bounded, and round the derived values in the children. Wrap `computeAlbumCharacter` in `useMemo([displayFingerprint])` so the `tags` and `rotatingDescriptions` identities are stable and `CharacterTags` memo works. Remove `transition: all` from the elements whose properties are being animated programmatically.

### D8-01: Back from album/artist/playlist detail still drops focus to <body>; playlist loading/error states have no h1
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/useNavigationState.ts:36-46`, `auralis-web/frontend/src/components/library/Details/DetailViewHeader.tsx:125-132`, `auralis-web/frontend/src/components/library/Details/PlaylistDetailView.tsx:71-160`
- **Status**: Regression of #6026 (closed with "(#6026, part)")
- **Description**: Commit 464e6fcd4 fixed only the "enter" half of #6026 (DetailViewHeader focuses its h1 on mount). Its message says "restoring the grid position on Back is not done", yet the issue was closed. #6026's acceptance criteria ("After Back, focus returns to the originating card (or at least the grid heading), not <body>") are unmet: the Back button (and the whole detail view) unmounts, `handleBackFromAlbum/Artist` only `setState(null)`, and nothing refocuses a card or the ViewContainer h1 (ViewContainer's `<h1>` has no `tabIndex`/ref). The commit message and test also claim "playlist" detail views are covered, but `PlaylistDetailView` does not render `DetailViewHeader`: it has its own inline h1 with no ref/focus, and its loading and error/not-found branches render no heading at all (EmptyState's Title is a plain Typography). Back from a playlist (`onBack={onBackToSongs}`) strands focus the same way.
- **Evidence**:
  ```ts
  // useNavigationState.ts
  const handleBackFromAlbum = useCallback(() => { setSelectedAlbumId(null); }, []);
  const handleBackFromArtist = useCallback(() => { setSelectedArtistId(null); setSelectedArtistName(''); }, []);
  ```
  ```tsx
  // PlaylistDetailView.tsx:156 — no ref, no tabIndex, no focus effect
  <Typography variant="h4" component="h1" sx={{...}}>{playlist.name}</Typography>
  ```
  `grep -rn "\.focus(" src --include=*.ts*` (non-test) shows no focus call tied to leaving a detail view.
- **Impact**: Keyboard/screen-reader user presses Back and lands on <body> with the whole page silently replaced and loses their place in a long grid (Tab restarts at the top bar). Playlist view enter is silent for the loading/error states.
- **Suggested Fix**: Make `ViewContainer`'s h1 focusable (`tabIndex={-1}` + focus on mount when returning from a detail view) or remember the originating card id in `useNavigationState` and refocus it after the grid remounts. Give `PlaylistDetailView` the same title-focus effect (or reuse `DetailViewHeader`) and render an h1 in its error/not-found branch.

### D8-02: Brand accent #7366F0 used as text colour fails WCAG AA in both themes; the #5675 `accentText` fix is overridden at its only table site
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Styles/Table.styles.ts:23-31`; `components/library/Items/tables/TrackTableRowItem.tsx:84-87`; `components/library/Views/ArtistTrackRow.tsx` (same StyledTableRow); `components/library/Styles/Tabs.styles.ts:32,54`; `components/library/Details/ArtistDetailTabs.tsx:60`; `components/shared/KeyboardShortcutsHelp.styles.ts:32,44`; `components/shared/SimilarTracksModal/SimilarTrackRow.tsx:70,106`; `components/shared/ContextMenu/PlaylistSection.tsx:40`; `components/library/Styles/ArtistList.styles.ts:59`; `components/playlist/DroppablePlaylist.styles.ts:58`; `components/playlist/PlaylistList.styles.ts:135,151`; `components/library/Items/artists/ArtistInfoModal.tsx:129`; `components/shared/DropZone/DropZoneText.tsx` (isDragging colour); `theme/semanticTheme.ts:107`
- **Status**: Regression of #5675 (closed; fix incomplete, sibling sweep not done)
- **Description**: #5675 introduced `themeVars.accentText` (light `#5B4FD6`, 5.65:1) but applied it at only two sites (TrackRow.styles.ts:124, TrackTableRowItem.tsx:86). (1) At the table site the fix is dead: `StyledTableRow` sets `'&.current-track .track-title' { color: tokens.colors.accent.primary }` (specificity 0,3,0), which beats the Typography `sx` colour (0,1,0), so the current-track title/number in AlbumTrackTable and ArtistTrackRow still render in raw `#7366F0`. (2) Roughly 20 other text sites (selected tab labels, shortcut keys/category titles, "% match", "Create new playlist", hovered artist name, playlist count, query highlight, stat values) read the static brand colour. (3) `accentText` in dark mode is itself `tokens.colors.accent.primary`, so dark mode was never fixed. Computed contrast: `#7366F0` on light canvas `#F8F9FD` 4.08:1 (white 4.30); on dark `#101729` 4.15, `#151D2F` 3.91, `#1A2338` 3.64, `#1F2940` 3.37; current-track table row (15% accent tint over the table surface) 3.30:1 dark / 3.41:1 light (with `accentText` it would be 4.72 in light). Normal-size text needs 4.5:1.
- **Evidence**:
  ```ts
  // Table.styles.ts:23-31
  '&.current-track': {
    '& .track-number': { color: tokens.colors.accent.primary },
    '& .track-title': { color: tokens.colors.accent.primary, fontWeight: tokens.typography.fontWeight.bold }
  }
  // TrackTableRowItem.tsx:86 — loses to the rule above
  color: isCurrentTrack ? themeVars.accentText : themeVars.textPrimary,
  // semanticTheme.ts:107 (dark)  accentText: tokens.colors.accent.primary,
  ```
- **Impact**: Now-playing highlight, selected tabs and several labels are below AA for low-vision users in light mode and on raised dark surfaces (WCAG 1.4.3).
- **Suggested Fix**: Make `accentText` a real text token in both themes (dark: `tokens.colors.accent.primaryLight` `#8B7CF7`, 5.4/5.1/4.7:1 on level1/2/3); delete the colour from `Table.styles.ts` `.current-track` rules (let the component's `accentText` win) and replace the static `tokens.colors.accent.primary` text colours listed above with `themeVars.accentText`. Extend `TextDisabledContrast.test.ts`-style guard to flag `color: tokens.colors.accent.primary`.

### D8-04: Track listbox: every row still contributes extra Tab stops, defeating the roving tabindex; interactive controls nested in role="option"
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `components/library/Items/tracks/TrackRow.tsx:126-190`, `components/library/Items/tracks/SelectableTrackRow.tsx:70-95`, `components/library/Items/tracks/TrackRowPlayButton.tsx:27-31`, `components/library/Views/TrackListViewContent.tsx:203-250`
- **Status**: NEW (related closed: #5011, #6069, #5658; the nested-interactive class was fixed for MediaCard in #5101 but not here)
- **Description**: TrackRow documents "exactly one row in the listbox is tabIndex=0 ... so Tab enters/exits the list in one stop" (TrackRow.tsx:30-33), but only the `role="option"` element is roving. Each mounted row also contains a MUI `Checkbox` input (`SelectableTrackRow`, native tabindex 0, opacity 0 until hover/focus), a Play `IconButton` and a More `IconButton` (default tabindex 0, no `tabIndex={-1}`). With ~20-40 mounted rows, Tab walks 3 extra stops per row before it can leave the list (and the count grows as the virtual window moves), and a Tab from the option lands on invisible-until-focused controls. Structurally, the `role="option"` (children presentational per ARIA; axe `nested-interactive`) contains two focusable buttons, and the checkbox is a child of the `listbox` outside any option, so the listbox owns a non-option child. The a11y.spec.tsx axe suite does not cover TrackRow/TrackListViewContent, so none of this is caught.
- **Evidence**:
  ```tsx
  // TrackRow.tsx
  <RowContainer tabIndex={tabIndex} role="option" aria-label={...}> ...
    <TrackRowPlayButton .../>   // <PlayButton ...> no tabIndex
    <MoreButton ... aria-label={`More options for ${track.title}`}>
  // SelectableTrackRow.tsx:73  <StyledCheckbox ... />  // sibling of the option, inside role="listbox"
  ```
- **Impact**: Keyboard users must press Tab dozens of times to pass the Songs list; screen readers may not expose the nested Play/More buttons inside an option.
- **Suggested Fix**: Take the per-row checkbox/Play/More out of the tab order (`tabIndex={-1}` on all three, `inputProps.tabIndex` for the checkbox) and expose their actions as keys on the focused option (Enter already plays and the ContextMenu key/Shift+F10 already opens the menu; add a key such as Ctrl+Space for toggling selection), or restructure to an APG grid (`role="grid"` rows with gridcells) which allows interactive cells. Add TrackListViewContent to the axe spec.

### D8-05: Escape in the "Reset Library?" ConfirmationDialog also closes the whole Settings dialog
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/a11y/focusManagement.ts:108-118`, `components/shared/ui/ConfirmationDialog.tsx:28-47`, `components/settings/AdvancedSettingsPanel.tsx:238-249`
- **Status**: NEW
- **Description**: `ConfirmationDialog` is rendered inline inside the Settings MUI `<Dialog>` (AdvancedSettingsPanel is a child of SettingsDialog's content). Its Escape handling comes from `focusManager.createFocusTrap`, a native `keydown` listener that calls `event.preventDefault(); onEscape()` but never `stopPropagation()`. The event continues to React's root, where MUI Modal's own `onKeyDown` (node_modules/@mui/material/Modal/useModal.js:105-123) explicitly "doesn't take event.defaultPrevented into account" and, because the Settings dialog is still the top MUI modal, calls `onClose(event, 'escapeKeyDown')`. One Escape therefore cancels the confirmation and closes Settings, discarding unsaved setting edits and moving focus away from the dangerous-section the user was in. (Found by code reading plus the MUI source; not executed.)
- **Evidence**:
  ```ts
  // focusManagement.ts
  if (event.key === 'Escape' && onEscape) { event.preventDefault(); onEscape(); return; }
  ```
  ```js
  // @mui/material/Modal/useModal.js
  if (event.key !== 'Escape' || event.which === 229 || !isTopModal()) return; ... onClose(event, 'escapeKeyDown');
  ```
- **Impact**: Keyboard users lose Settings state when they only meant to dismiss the confirmation (APG: Escape closes only the topmost dialog).
- **Suggested Fix**: Call `event.stopPropagation()` after handling Escape in the focus trap (React 18 synthetic events still see it only if stopped at the native layer on a node below the React root, which is the case here), or render ConfirmationDialog through a portal outside the MUI Dialog and mark the Settings dialog `disableEscapeKeyDown` while it is open. Add a test that Escape in the confirm leaves Settings mounted.

### D8-06: Single-character global shortcuts (m, 1, 2, 3, /, ?) cannot be turned off or remapped
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/hooks/app/useAppShortcuts.ts:61-197`, `auralis-web/frontend/src/ComfortableApp.tsx:118-124`, `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:106-116`
- **Status**: NEW
- **Description**: WCAG 2.1.4 (Level A) requires that a shortcut made of a single printable character be switchable off, remappable, or active only while its component has focus. `useAppShortcuts` registers `m` (mute), `1`/`2`/`3` (switch view), `/` (focus search) and `?` (help) as window-level shortcuts with no modifier (plus unmodified Space and arrows). `useKeyboardShortcuts` already implements `enable()/disable()` (`keyboardShortcuts.enable/disable`), but `ComfortableApp` destructures only `shortcuts, isHelpOpen, openHelp, closeHelp, formatShortcut`, and the Settings dialog has no toggle; the KeyboardShortcutsHelp text even says "Enable keyboard shortcuts in settings" (KeyboardShortcutsEmpty.tsx) although no such setting exists. The service skips text inputs and open overlays, which mitigates but does not satisfy the criterion (speech-input users cannot avoid accidental triggers by spoken letters).
- **Evidence**:
  ```ts
  // useAppShortcuts.ts
  { key: 'm', description: 'Mute/Unmute', ... }, { key: '1', ... }, { key: '2', ... }, { key: '3', ... }, { key: '/', ... }, { key: '?', ... }
  // ComfortableApp.tsx:118-124 — enable/disable never consumed
  const { shortcuts, isHelpOpen, openHelp, closeHelp, formatShortcut } = useKeyboardShortcuts(keyboardShortcutsArray);
  ```
- **Impact**: Dictation/speech-control and some switch users trigger mute/navigation unintentionally; fails SC 2.1.4.
- **Suggested Fix**: Add an "Enable single-key shortcuts" switch in InterfaceSettingsPanel wired to the existing `enable()/disable()` (persist in UserSettings), or move m/1/2/3 behind a modifier. Fix the dangling copy in KeyboardShortcutsEmpty.


## LOW (44)

### D1-01: CozyLibraryView regrew from 289 to 335 lines after its #5840 split; the LOC ratchet froze the overshoot
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:1-335` (component body 69-331, one 263-line `memo` arrow)
- **Status**: Regression of #5840
- **Description**: #5840 (closed) split CozyLibraryView after it crossed 300. The fix commit f4e303aa1 left it at 289 lines. Later feature and fix commits regrew it: a31e694a0 (#6007) 299, 24877c825 (#5866) 314, 3446dbcb9 (#6011) 317, 79c085a3c (#6010) 332, 957b9045f (#6014 follow-up) 335. The component still owns, in one function, the debounced search state, the client-side filter, seven hook compositions (library data, selection, navigation, playback, metadata editing, similar-tracks modal, batch ops), the view-routing early return, the view header config, batch toolbar, empty/list branching and two lazy dialogs. On 2026-11-17 commit 1558a59e6 (#6267) wrote `"CozyLibraryView.tsx": 335` into `loc-ceilings.json`, so the ratchet now treats 335 as the allowed size instead of the 300 rule.
- **Evidence**:
```
$ git show f4e303aa1:auralis-web/frontend/src/components/library/CozyLibraryView.tsx | wc -l   -> 289
$ wc -l auralis-web/frontend/src/components/library/CozyLibraryView.tsx                           -> 335
loc-ceilings.json:65:    "auralis-web/frontend/src/components/library/CozyLibraryView.tsx": 335,
```
- **Impact**: The one shipped frontend file over the project's 300-line limit keeps taking every library-view behaviour change; the next fix lands on a file already waived. Maintenance cost only; no runtime effect.
- **Suggested Fix**: Move the debounce plus client filter into a `useLibrarySearch(searchQuery, tracks)` hook (see D1-03, which also removes the duplicate debounce) and the two lazy dialogs with their open-state hooks into a `LibraryDialogs` child (see D1-04). That brings the file under 300, after which the ceiling can be lowered back.

### D1-02: Hooks that #6275 listed (and others it never listed) still hold single functions of 130-220 lines
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `hooks/enhancement/useEnhancedStreamStart.ts:67-286`; `hooks/library/useLibraryPagination.ts:36-237`; `hooks/enhancement/useAudioStreamingCore.ts:79-248`; `hooks/enhancement/useEnhancementCommands.ts:46-214`; `hooks/websocket/useWebSocketConnection.ts:64-232`; `contexts/PlaybackSessionContext.tsx:42-199`; `hooks/player/usePlayerStateSync.ts:54-186`; `hooks/enhancement/useStreamMessageHandlers.ts:66-194`; `components/settings/useSettingsDialog.ts:24-202`; `components/library/EditMetadataDialog/useMetadataForm.ts:47-208`
- **Status**: NEW (the first two groups are the unmet remainder of closed #6275; `useEnhancedStreamStart`, `useSettingsDialog`, `useMetadataForm` were never in its list)
- **Description**: #6275 was closed on 2026-11-17 after splitting ten hooks, with the stated caveat "the longest remaining function is 202 lines". The issue's own acceptance bar was 120 lines per function. Re-measured at HEAD: `useLibraryPagination` 202, `useAudioStreamingCore` 170, `useEnhancementCommands` 169, `useWebSocketConnection` 169, `PlaybackSessionProvider` 158, `usePlayerStateSync` 133, `useStreamMessageHandlers` 129. Several are comment-heavy (code-line counts 72-142), so the residual is smaller than the raw figures, but the bar is not met. The worst case is outside #6275's list: `useEnhancedStreamStart` is a single `useCallback` spanning lines 74-283 (210 raw, 119 code lines). It handles two disjoint paths inline: the "resume into an existing buffer after a seek or reconnect" path (lines 100-142, early `return`) and the "build a new PCMStreamBuffer, AudioContext and AudioPlaybackEngine" path (lines 144-282). It ends in an `eslint-disable react-hooks/exhaustive-deps` whose dependency list is `[dispatch, core.handleChunk, playerVolume, playerIsMuted]` although the body touches about ten more `core.*` members (safe only because they are refs). The sibling `useEnhancedPlayCommand` is 127 lines. `useSettingsDialog` (147 code lines) and `useMetadataForm` (121 code lines) each mix load, edit buffer, save, reset and folder operations in one function.
- **Evidence**:
```
useEnhancedStreamStart.ts:74   const handleStreamStart = useCallback((message: AudioStreamStartMessage) => {
useEnhancedStreamStart.ts:100      if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) { ... return; }   // resume path
useEnhancedStreamStart.ts:144      core.pcmBufferRef.current?.dispose();  const buffer = new PCMStreamBuffer(...)          // rebuild path
useEnhancedStreamStart.ts:283   }, [dispatch, core.handleChunk, playerVolume, playerIsMuted]);
```
- **Impact**: The stream-start handler is on the playback path and has collected a fix per seek/epoch/gain bug (#5607, #5860, #5861, #5862, #5931 are all cited inline). Each future fix edits one 210-line closure whose two paths share locals (`isSeek`, `seekPosition`), so a change to one path is easy to apply to the wrong branch. No current defect.
- **Suggested Fix**: Split `useEnhancedStreamStart` into `resumeIntoExistingBuffer(core, message, dispatch)` and `buildStreamEngine(core, message, {volume, muted}, dispatch)` as plain functions in a sibling module such as `streamStartSteps.ts`, leaving the callback about 30 lines. Extract the engine creation and listener wiring (lines 144-246) first, since it is the longest block. Treat the rest as ceiling-tracked rather than a new ticket per hook.

### D1-03: Library search is debounced twice, and the second debounce is a re-typed 250 ms literal beside `SEARCH_DEBOUNCE_MS` (300 ms)
- **Severity**: LOW
- **Dimension**: Component Quality (cross-references API Client / Hook dimensions)
- **Location**: `components/library/CozyLibraryView.tsx:81-85` and `components/core/useSearchInput.ts:48`
- **Status**: NEW
- **Description**: The top-bar search field debounces with `SEARCH_DEBOUNCE_MS` (300 ms, `config/timing.ts:23`) before it calls `onSearch`, which is `setSearchQuery` in `ComfortableApp.tsx:168`. `CozyLibraryView` then runs a second `setTimeout(..., 250)` on that already-debounced `searchQuery` before sending it to the backend as `debouncedSearch`. The #5866 comment says the debounce stops "a request per keystroke" and that the client filter "runs on the un-debounced value for instant feedback". Neither holds: `searchQuery` is already debounced upstream, so the client filter lags by 300 ms and the request by about 550 ms. The 250 literal is also a debounce that does not come from `config/timing.ts` (#5800).
- **Evidence**:
```
// useSearchInput.ts:48
debounceRef.current = setTimeout(() => onSearch(query), SEARCH_DEBOUNCE_MS);   // 300 ms -> setSearchQuery
// CozyLibraryView.tsx:81-85
const [debouncedSearch, setDebouncedSearch] = useState(searchQuery);
useEffect(() => {
  const t = setTimeout(() => setDebouncedSearch(searchQuery), 250);
  return () => clearTimeout(t);
}, [searchQuery]);
```
- **Impact**: About 250 ms of avoidable extra latency between the end of typing and the server-backed result, and the "instant feedback" claim is false. Clearing the box with Escape or the clear button also leaves the previous server-filtered list on screen for the extra 250 ms plus the fetch.
- **Suggested Fix**: Drop the local debounce and pass `searchQuery` straight to `useLibraryWithStats` (the top bar already debounces), or move debouncing into one place and use `SEARCH_DEBOUNCE_MS` there. Correct the #5866 comment either way.

### D1-04: Library dialogs have neither a local ErrorBoundary nor `lazyWithRetry`, so a failed dialog chunk is unrecoverable and a dialog render crash takes the whole library region down
- **Severity**: LOW
- **Dimension**: Component Quality (Error boundaries)
- **Location**: `components/library/CozyLibraryView.tsx:27-28, 290-318`; sibling `components/shared/ui/feedback/EmptyState.tsx:73`
- **Status**: NEW
- **Description**: The route-level lazies in `ComfortableApp.tsx:12-14` use `lazyWithRetry` (#6035), and Settings and Shortcuts-help each sit in their own boundary (#4880). `EditMetadataDialog` and `SimilarTracksModal` are still bare `lazy()` and are rendered inside `CozyLibraryView`, whose only enclosing boundary is the library-region one (`ComfortableApp.tsx:188`). Two consequences. (1) A rejected chunk load is cached by `lazy()`. The library boundary's "Try again" remounts `CozyLibraryView` (state is reset, the dialog closed), but opening the dialog again re-renders the same rejected lazy and throws into the boundary again until the app reloads. This is exactly the regression class #6035 fixed for routes. `lazyWithRetry` would work here, because it reads `ErrorBoundaryResetContext` from that same boundary. (2) A render error inside either dialog unmounts the track list, selection and scroll position, rather than just the dialog. `EmptyState.tsx:73` has the same bare-`lazy` DropZone import, but its fallback sits under the same region boundary, and Electron serves chunks locally, so a failure is unlikely in practice.
- **Evidence**:
```
// CozyLibraryView.tsx:27-28
const EditMetadataDialog = lazy(() => import('./EditMetadataDialog/EditMetadataDialog'));
const SimilarTracksModal = lazy(() => import('@/components/shared/SimilarTracksModal').then((m) => ({ default: m.SimilarTracksModal })));
// ErrorBoundary appears only in index.tsx, ComfortableApp.tsx (x4), Player.tsx and core/ErrorBoundary.tsx
```
- **Impact**: Low likelihood (local chunks), but when it hits, the edit-metadata and find-similar dialogs stay broken for the rest of the session and the library flashes the region error fallback each time.
- **Suggested Fix**: Use `lazyWithRetry` for the three dialog and DropZone imports, and wrap each dialog's mount in a small `ErrorBoundary` with `RegionErrorFallback` whose retry closes the dialog first (the Settings pattern at `ComfortableApp.tsx:219-233`).

### D1-05: Track-row callbacks are drilled through three intermediate components
- **Severity**: LOW
- **Dimension**: Component Quality (Prop drilling)
- **Location**: `components/library/CozyLibraryView.tsx:279-292` -> `Views/TrackListView.tsx:116-125` -> `Views/TrackListViewContent.tsx:240-251` -> `Items/tracks/SelectableTrackRow.tsx:75-92` -> `Items/tracks/TrackRow.tsx:62-102` -> `useTrackContextMenu.ts`
- **Status**: NEW
- **Description**: `onEditMetadata` and `onFindSimilar` are created in `CozyLibraryView` and consumed only by `useTrackContextMenu` inside `TrackRow`. They pass through `TrackListView`, `TrackListViewContent` and `SelectableTrackRow`, each declaring the props and forwarding them unchanged. `onPause`, `onTrackPlay` and the selection callbacks travel the same chain. That is three pass-through layers (the checklist threshold is more than two), and each layer has to be edited and re-memoised when a menu action is added. The grid mode drops them entirely: `TrackListView` renders `<TrackGridView tracks onTrackPlay>` only (lines 106-108), so the default `viewMode='grid'` has no edit-metadata, find-similar or selection path, and no playing-state indication on the cards.
- **Evidence**:
```
TrackListView.tsx:121          onEditMetadata={onEditMetadata}
TrackListViewContent.tsx:247   onEditMetadata={onEditMetadata}
SelectableTrackRow.tsx:90      onEditMetadata={onEditMetadata}
TrackRow.tsx:101               onEditMetadata,   // -> useTrackContextMenu
```
- **Impact**: Maintenance friction on the library hot path. The grid-mode gap is a possible product gap (the `TrackListViewProps` comment says selection is "for list view"); I did not verify whether grid mode is intended to be read-only.
- **Suggested Fix**: Provide the row actions (edit, find-similar, play, pause) through a small `TrackRowActionsContext` set in `CozyLibraryView`, so `TrackRow` reads them directly and the three pass-through components keep only list concerns.

### D1-06: Two independent roving-tabindex implementations for virtualized lists, with diverging robustness
- **Severity**: LOW
- **Dimension**: Component Quality (single responsibility / DRY)
- **Location**: `components/library/Views/TrackListViewContent.tsx:63-218` and `components/player/QueuePanel/useQueueRovingFocus.ts:1-90`
- **Status**: NEW
- **Description**: The queue extracted its roving focus as `useQueueRovingFocus` (#6027, "as the library listbox got in #5011"). The library listbox still carries its own copy inline in `TrackListViewContent`: `activeIndex` state, the tab-stop clamp into the mounted virtual window (#6069), `handleListboxKeyDown` for ArrowUp, ArrowDown, Home and End, `handleListboxFocus`, and a focus-retry effect. Both do the same job, with different guarantees. The library copy has a bounded, cancellable rAF retry (#5634) and a portal-bubbling guard (#6024). The queue copy focuses via a single un-cancelled `requestAnimationFrame(() => find()?.focus())` and has no `contains(target)` guard. A fix to one (as #6069 and #6024 were) has to be re-derived for the other. The inline copy also accounts for about 150 of `TrackListViewContent`'s 229 lines, which keeps a list-rendering component doing focus management as well.
- **Evidence**:
```
// TrackListViewContent.tsx
const [activeIndex, setActiveIndex] = useState(0);
const tabStopIndex = firstItem && lastItem ? Math.min(Math.max(activeIndex, firstItem.index), lastItem.index) : activeIndex;
...
// useQueueRovingFocus.ts
const [activeIndex, setActiveIndex] = useState(0);
const tabStopIndex = first && last ? Math.min(Math.max(clamped, first.index), last.index) : clamped;
requestAnimationFrame(() => find()?.focus());
```
- **Impact**: Accessibility fixes land in one list and silently miss the other; the queue lacks the unmount-safe retry and portal guard.
- **Suggested Fix**: Generalise `useQueueRovingFocus` into a shared `useVirtualRovingFocus({ count, scrollElementRef, virtualizer, rowAttr })` in `src/a11y/` or `hooks/shared/`, with the library's bounded-retry and containment guard, and use it in both.

### D2-02: `reconcileQueueIndex` trusts any engine slot holding the playing track's id, so a queue with duplicate tracks jumps back to the engine's slot
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/hooks/player/queueIndexReconciliation.ts:119-142` (callers `playerStateSnapshot.ts:122`, `useQueueSubscription.ts:70`)
- **Status**: NEW (sibling of closed #5600, which fixed the same duplicate-id ambiguity only in `setCurrentTrackAndSyncQueue`)
- **Description**: `setCurrentTrackAndSyncQueue` resolves a duplicate id by the distance to the local `queue.currentIndex` (`playerQueueSync.ts:354-373`). `reconcileQueueIndex` has no access to the local index: it accepts `engineIndex` whenever `tracks[engineIndex].id === playingTrackId`, and otherwise picks the matching slot nearest to the engine pointer. The engine pointer is exactly the value known to be stale after local navigation (#5937), so the anchor is wrong.
- **Evidence**:
  ```ts
  if (tracks[engineIndex]?.id === playingTrackId) return engineIndex;   // slot 0 is "A", playing slot 2 is also "A"
  ...
  const distance = Math.abs(i - engineIndex);                           // anchored on the stale engine pointer
  ```
  The spec pins this: `queueIndexReconciliation.test.ts:27-32` expects `reconcileQueueIndex(tracks, 0, 2) === 1` where the user could be at slot 3.
- **Impact**: Queue [A,B,A,C] (a track queued twice is legitimate, per #5600). User Next-skips to slot 2 (engine pointer still 0). Any snapshot (shuffle toggle, repeat toggle, reconnect push, `queue_changed`) reconciles to slot 0 because `tracks[0].id` equals the playing id. Redux index moves 2 -> 0 and the following Next plays B, making C unreachable until another skip. Needs duplicate ids and a post-skip snapshot, hence LOW.
- **Suggested Fix**: Add the local index as an input: `reconcileQueueIndex(tracks, engineIndex, playingTrackId, localIndex)`; return `localIndex` when `tracks[localIndex]?.id === playingTrackId`, else fall back to the nearest slot to the local index (the same rule as `resolveQueueIndex`). Share one resolver between this file and `playerQueueSync.ts`.

### D2-03: Three queue selectors have no production consumer (residue of #6040 / #6208)
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/store/selectors/queue.ts:20-37` (and the comments at `store/slices/queueSlice.ts:288-289`)
- **Status**: NEW (#6040 and #6208 are CLOSED; their deletions left these behind, and the #6040 commit message wrongly lists `selectFormattedRemainingTime` as having a production importer)
- **Description**: A grep for `selectRemainingTime|selectTotalQueueTime|selectFormattedRemainingTime` across `src/` (non-test) finds only the definitions, comments, and `store/selectors/__tests__/selectors.test.ts` (plus `formatHumanDuration`, which then exists in `utils/timeFormat.ts` only for `selectFormattedRemainingTime` among selectors). The only production reads of the queue slice are `selectQueueTracks/CurrentIndex/IsShuffled/RepeatMode/LastUpdated` (slice-local) and `selectCurrentQueueTrack`. The audit checklist treats a selector with no production consumer as a finding.
- **Evidence**:
  ```ts
  export const selectRemainingTime = createSelector(...)        // queue.ts:20  - only used by selectFormattedRemainingTime + test
  export const selectTotalQueueTime = createSelector(...)       // queue.ts:26  - test only
  export const selectFormattedRemainingTime = createSelector(...) // queue.ts:31 - test only
  ```
  Each also recomputes an O(n) reduction over `queue.tracks` (up to 50 000 entries) whenever `tracks` changes if anyone ever subscribes.
- **Impact**: Dead code with its own spec keeps the "memoized queue-time selectors" story alive and misleads the next reader (the comments in `queueSlice.ts` and `playerQueueSync.ts` cite them as live consumers of the #4580 duration sync).
- **Suggested Fix**: Delete the three selectors, their describe blocks in `selectors.test.ts`, the now-orphaned `formatHumanDuration` import, and fix the two comments; or wire a real consumer (a queue footer showing remaining time) and keep them.

### D2-04: `store/__tests__/testFixtures.ts` (417 lines) is consumed only by its own spec and hand-lists the four slices
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/store/__tests__/testFixtures.ts:271-306` (+ `testFixtures.test.ts`, 335 lines)
- **Status**: NEW (#5681 is CLOSED; it fixed `test/test-utils.tsx` to use the exported `reducer` map but left this second harness)
- **Description**: The module exports a second `createTestStore` (same name as `test/test-utils.tsx`) and `createStoreFromFixture`, each built with a hand-written `reducer: { player, queue, cache, connection }` map, default middleware only (no error-tracking middleware as in production), and fixtures typed `Partial<any>`. Its only importer is `testFixtures.test.ts`; no other spec imports it. A slice added to `store/index.ts` would be missing here, which is the exact drift #5681 closed for the shared harness.
- **Evidence**:
  ```ts
  return configureStore({
    reducer: { player: playerReducer, queue: queueReducer, cache: cacheReducer, connection: connectionReducer },
    preloadedState: preloadedState as RootState,
  });
  ```
  `grep -rn "testFixtures" src` returns only the file itself and `testFixtures.test.ts`.
- **Impact**: ~750 lines of test scaffolding that tests only itself, with a duplicate `createTestStore` that can be auto-imported by mistake and silently build a production-divergent store. (Other specs that hand-list a subset of slices, e.g. `deterministic-timestamps.test.ts`, `durationQueueSync.test.ts`, do so deliberately for slice isolation and are not reported.)
- **Suggested Fix**: Delete `testFixtures.ts` and its spec, or, if any fixture is wanted, rebuild its stores from `reducer` exported by `@/store` and import `createTestStore` from `test-utils`.

### D2-05: `useQueueSubscription` handles wire keys the backend never emits, including an un-reconciled `queue_shuffled.tracks` branch
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:80-93`; `auralis-web/frontend/src/types/ws/queue.ts:54-76`
- **Status**: NEW (same class as closed #4787/#5637 phantom keys and #6260; not covered by an open issue)
- **Description**: The backend payloads are `QueueShuffledPayload = {is_shuffled}` and `RepeatModeChangedPayload = {repeat_mode}` (`backend/websocket/outbound/queue.py:51-56`; both emitters in `queue_order_mixin.py:184,232` send only `{"is_shuffled": ...}`). The frontend additionally reads `isShuffled`, `repeatMode`, and `tracks` on these messages and the types declare them. The `tracks` branch dispatches `setQueue(...)` with no #5601 index reconciliation, so if a backend ever started populating it, it would reintroduce the stale-pointer clobbering that the `queue_changed` branch above it guards against.
- **Evidence**:
  ```ts
  if (data.is_shuffled != null) dispatch(reduxSetIsShuffled(data.is_shuffled));
  else if (data.isShuffled != null) dispatch(reduxSetIsShuffled(data.isShuffled));   // never sent
  if (data.tracks) dispatch(reduxSetQueue(data.tracks.map(mapTrackInfoToTrack)));   // never sent, no reconcile
  ```
- **Impact**: Dead, untested-by-reality branches that advertise a wire contract that does not exist; the latent `tracks` branch is an unreconciled `setQueue`/`currentIndex` writer.
- **Suggested Fix**: Drop `isShuffled`, `repeatMode` and `tracks` from `QueueShuffledMessage`/`RepeatModeChangedMessage` and the handler (queue contents arrive via `queue_changed`), or route `tracks` through the same `setQueue` + `reconcileQueueIndex` path as `queue_changed`.

## Existing issues confirmed (not re-filed)

### D3-04: useWebSocketConnection re-arm path increments the singleton refCount without a matching decrement
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:93-96` (increment in `connect`), `:179-191` (single decrement in `disconnect`), `:216` (`useReconnectOnNetwork(..., connect)`); `auralis-web/frontend/src/hooks/websocket/useReconnectOnNetwork.ts:15-18`; also `auralis-web/frontend/src/components/shared/ConnectionStatusIndicator.tsx:73,173` (context `connect`)
- **Status**: NEW
- **Description**: `refCount` is meant to count mounted providers (incremented in the mount effect, decremented in its cleanup), but the increment lives inside `connect()` itself. `useReconnectOnNetwork` calls `connect()` again on `online`/`visibilitychange` after the manager gave up (and the context exposes `connect` to consumers), so each re-arm adds one count that no cleanup removes.
- **Evidence**:
```ts
const connect = useCallback(async () => {
  connState.refCount++;                       // also runs for every network-retry / manual connect()
...
const disconnect = useCallback(() => {
  connState.refCount = Math.max(0, connState.refCount - 1);   // once, at unmount
  if (connState.refCount === 0 && connState.manager) { closeCurrentManager(); }
```
- **Impact**: After one give-up/retry cycle `refCount` is 2 with one provider; at provider unmount the count only drops to 1, so the new singleton WebSocket (socket, heartbeat timer, handlers) is never closed. Production has a single app-lifetime provider so the visible effect is limited to teardown, HMR remounts and tests (leaked connections across tests is what `resetConnectionSingletons` exists to paper over).
- **Suggested Fix**: Move the refCount increment into the mount effect (or make `connect()` for retry paths a separate function that does not touch the count).

### D3-05: A user pause issued while AudioPlaybackEngine.startPlayback() is awaiting is dropped and playback starts anyway
- **Severity**: LOW
- **Dimension**: Hook Correctness (single-flight playback start)
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:90-93,147-150` (start / pause), `auralis-web/frontend/src/hooks/enhancement/usePlaybackTransport.ts:90-94` (`pausePlayback`), `auralis-web/frontend/src/hooks/enhancement/streamingCoreLifecycle.ts` (`startPlaybackWhenBuffered`; `pauseHoldRef` read only at call time)
- **Status**: NEW (gap in the #6043 single-flight design: stop/dispose cancel the attempt, pause does not)
- **Description**: `start()` awaits `AudioContext.resume()` and `bufferScheduler.ensureReady()` (worklet load) before `setState('playing')`. `AudioPlaybackEngine.pausePlayback()` returns immediately when `positionTracker.isPlaying()` is false, which is the case for that whole window. The hook still sets `pauseHoldRef=true` and `isPaused=true`, but the in-flight attempt only compares `startAttempt` (bumped by stop/dispose, not by pause), so it proceeds to `createProcessor()` and `setState('playing')`; the `onStateChanged('playing')` callback then does `core.setIsPaused(false)`.
- **Evidence**:
```ts
pausePlayback(): void {
  if (!this.positionTracker.isPlaying()) { return; }      // state is still 'stopped' while start() awaits
...
if (attempt !== this.startAttempt) return; // only stop/dispose bump startAttempt
this.bufferScheduler.createProcessor(); ... this.positionTracker.setState('playing');
```
- **Impact**: A pause clicked during the first-play startup window (context resume / worklet load) is silently lost: audio starts although the user paused, and the UI flips back to "playing". Narrow window, no data loss.
- **Suggested Fix**: Treat pause as a cancellation reason for the in-flight attempt (bump `startAttempt` in `pausePlayback()` when `this.starting` is set, and re-run the auto-start rule on resume), or re-check `pauseHoldRef` after the awaits.

### D3-06: Streaming hooks list the whole `wsContext` object in dependency arrays, so callback identities churn on every WS status flicker
- **Severity**: LOW
- **Dimension**: Hook Correctness (callback identity stability)
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:210`, `useStreamChunkHandler.ts:144`, `useStreamMessageHandlers.ts:191`, `useEnhancedSeek.ts:112`, `useAudioStreamingCore.ts:156` (flow-drain effect)
- **Status**: NEW (the documented #4608 / #4668 / #5621 convention is to depend on `wsContext.send` / `subscribe` / `setResumePositionGetter`, which are identity-stable; `usePlaybackTransport.ts:~145` already does this)
- **Description**: The provider re-memoizes the context value on every `isConnected`/`connectionStatus` change, so `wsContext` is a new object per flicker. The listed hooks close over the object (using only stable members plus `isConnected` in places), so `playEnhanced` -> `startTrackForSettings` -> `startTrack`/`followRemovedTrack`/`handleNext` -> `controlsValue` all change identity on each connect/disconnect, and `startFlowDrainWatch` is torn down and re-armed (its 250 ms phase resets).
- **Evidence**:
```ts
// useEnhancedPlayCommand.ts deps
[ wsContext, dispatch, currentTrackInfoRef, resetFingerprint, ... ]
// useAudioStreamingCore.ts
useEffect(() => startFlowDrainWatch({ flowPausedRef, pcmBufferRef, send: wsContext.send }), [flowPausedRef, pcmBufferRef, wsContext]);
```
- **Impact**: Extra re-renders of every PlaybackControls consumer and effect re-runs in `useAutoAdvance` on each WS state change; no functional break found (the auto-advance latch absorbs it). Mild perf/consistency issue.
- **Suggested Fix**: Destructure `send`, `reissueActiveStreamAs`, `isConnected` (via ref where only read at call time) and depend on those.

### D3-07: useArtworkRevision passes a fresh `subscribe` closure to useSyncExternalStore on every render
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:112`
- **Status**: NEW
- **Description**: `useSyncExternalStore((listener) => subscribeToAlbum(albumId, listener), ...)` creates a new `subscribe` function each render; React unsubscribes and resubscribes whenever that identity changes. The hook runs per album card (and per `useArtworkPalette`), so a 500-card grid re-subscribes 500 times on every re-render of the grid.
- **Evidence**:
```ts
return useSyncExternalStore(
  (listener) => subscribeToAlbum(albumId, listener),   // new function every render
  () => getRevisionSnapshot(albumId),
```
- **Impact**: Wasted Set/Map churn per render; no missed update (React re-reads the snapshot after resubscribing). Cosmetic cost on large grids.
- **Suggested Fix**: `const subscribe = useCallback((l) => subscribeToAlbum(albumId, l), [albumId]);`

### D3-08: Side effects inside functional setState updaters (useTrackSelection, useRecentlyTouched, useDropZone)
- **Severity**: LOW
- **Dimension**: Hook Correctness (purity)
- **Location**: `auralis-web/frontend/src/hooks/library/useTrackSelection.ts:119` (`setLastSelectedId` inside the `setSelectedTracks` updater), `auralis-web/frontend/src/hooks/library/useRecentlyTouched.ts:104` (`localStorage` write inside the `setRecentAlbums` updater), `auralis-web/frontend/src/components/shared/DropZone/useDropZone.ts:50` (`setIsDragging(false)` inside the `setDragCounter` updater)
- **Status**: NEW
- **Description**: Updater functions must be pure; React may call them twice (StrictMode, which `index.tsx` enables) or defer them to the render phase. Each of these performs a second state update or a storage write from inside the updater.
- **Evidence**:
```ts
setSelectedTracks((prev) => { ...; setLastSelectedId(trackId); return newSelection; });
setRecentAlbums(prev => { ...; saveRecentlyTouched(updated); return updated; });
setDragCounter((prev) => { const n = prev - 1; if (n === 0) setIsDragging(false); return n; });
```
- **Impact**: Currently idempotent, so no visible bug; duplicate storage writes and render-phase cross-state updates in dev, and a trap for the next edit. 
- **Suggested Fix**: Compute the next value outside the updater (refs for the previous value) and run the side effect after the `set` call or in an effect.

### D4-01: Preset typed as bare `string` on outgoing WS commands and the Enhancement settings panel
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/ws/commands.ts:15,34,51`; `auralis-web/frontend/src/components/settings/EnhancementSettingsPanel.tsx:9`
- **Status**: NEW (same class as closed #6051/#5610, which fixed the settings-write path but not these sites; the commands file arrived later in #6050)
- **Description**: The checklist makes "a preset typed as bare `string`" a finding. `PlayEnhancedCommand.data.preset`, `SeekCommand.data.preset` and `StreamOverrides.preset` are `string`, although every producer (`useEnhancementCommands.reissueEnhanced`, `usePlayEnhanced.startPlayback`) is typed `EnhancementPreset` and the backend (`ws_handlers/enhancement_params.py:66-72`) only accepts `VALID_PRESETS`, degrading anything else to the default with a warning. `EnhancementSettingsPanel` takes `defaultPreset: string` while `UserSettings.default_preset` is `EnhancementPreset`, so `SettingsDialogContent` passes a narrow type into a wide prop and the panel re-narrows with `isEnhancementPreset(e.target.value)` only on the way out.
- **Evidence**:
  ```ts
  // types/ws/commands.ts
  data: { track_id: number; preset?: string; intensity?: number; force?: boolean; start_position?: number; }
  data: { track_id: number; position: number; preset?: string; intensity?: number };
  export interface StreamOverrides { preset?: string; ... }
  // EnhancementSettingsPanel.tsx:9
  defaultPreset: string;
  ```
- **Impact**: A removed or misspelled preset name (`'warm'`) compiles into an outgoing command and is only caught server-side (silently ignored with a log line), which is exactly the failure the preset narrowing of 2026-09-13 tried to make compile-time.
- **Suggested Fix**: `preset?: EnhancementPreset` in the three command shapes and `defaultPreset: EnhancementPreset` in the panel (import from `@/types/domain`, as `types/ws/enhancement.ts` already does).

### D4-02: Design-system controls expose widened callback value types, forcing consumer casts
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/design-system/primitives/SegmentedControl.tsx:25-45`; `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:30-34,183`; siblings `components/settings/EnhancementSettingsPanel.tsx:75`, `PlaybackSettingsPanel.tsx:72,106`, `InterfaceSettingsPanel.tsx:51`
- **Status**: NEW
- **Description**: `SegmentedControl` is non-generic (`value: string`, `onChange: (value: string) => void`, `options: SegmentedControlOption[]` with `value: string`). Its only consumer keeps a closed union `AlbumSortOption = 'az' | 'year' | 'era'` and bridges with `setSortBy(value as AlbumSortOption)`; `ALBUM_SORT_OPTIONS` is an untyped `{value: string}[]`, so nothing ties the option list to the union. `CozyAlbumGrid` then indexes `SERVER_ORDER[sortBy]` and spreads the result into the query, so an option added to the array without the union/table entry type-checks and yields `...undefined` (sort silently ignored). The same widen-then-cast shape appears at the three settings sliders (`v as number`, MUI gives `number | number[]`) and the theme `Select`.
- **Evidence**:
  ```tsx
  // LibraryViewRouter.tsx
  const ALBUM_SORT_OPTIONS = [ { value: 'az', label: 'A-Z' }, { value: 'year', label: 'Year' }, { value: 'era', label: 'Era' } ];
  onChange={(value) => setSortBy(value as AlbumSortOption)}
  // SegmentedControl.tsx
  value: string;  onChange: (value: string) => void;  options: SegmentedControlOption[];
  ```
- **Impact**: No current runtime bug; the casts are what stop the compiler flagging an option/union drift.
- **Suggested Fix**: Make `SegmentedControl<T extends string>` generic (`value: T`, `onChange: (v: T) => void`, `options: {value: T; label: ReactNode}[]`) and type `ALBUM_SORT_OPTIONS` as `readonly {value: AlbumSortOption; label: string}[]`; for single-thumb sliders narrow with `typeof v === 'number'` or give the design-system `Slider` a `(value: number) => void` wrapper. `InterfaceSettingsPanel.tsx:51`'s cast is already a no-op (see D4-03).

### D4-03: Redundant `as` assertions defeat the style-table exhaustiveness they sit next to
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `design-system/primitives/Badge.tsx:77`, `Card.tsx:110-111`, `Button.tsx:179-180`, `IconButton.tsx:155-156`, `Input.tsx:153-154`, `Slider.tsx:141-142`; `shouldForwardProp` `prop as string` at `Card.tsx:53`, `Button.tsx:62`, `IconButton.tsx:52`, `Input.tsx:54`, `Slider.tsx:43`; plus `components/shared/ui/media/AlbumArtDisplay.tsx:116`, `hooks/websocket/socketFrameParser.ts:133`, `store/middleware/loggerMiddleware.ts:183`, `components/settings/useSettingsDialog.ts:178`, `components/settings/InterfaceSettingsPanel.tsx:51` (all under `auralis-web/frontend/src/`)
- **Status**: NEW (closed #6053 removed six other casts of this kind; these are different sites, not a regression)
- **Description**: The compiler API reports the operand type as identical to the asserted type at all of these (e.g. `"sm"|"md"|"lg" => "sm"|"md"|"lg"`, `string => string`, `AudioChunkMetaMessage => AudioChunkMetaMessage`, `string|number => string|number`). In the primitives the pattern is `variantStyles[variant as keyof typeof variantStyles]`: today a no-op, but if a variant is later added to the prop union without a table entry, `variant as keyof typeof variantStyles` turns the missing-key compile error into a silent `...undefined` spread (unstyled control). `socketFrameParser.ts:133` re-casts a value already narrowed by `message.type === 'audio_chunk_meta'` on the line above (the next line assigns `message` uncast to `pendingMeta`, proving the narrowing works).
- **Evidence**:
  ```ts
  ...sizeStyles[normalizedSize as keyof typeof sizeStyles],     // Button.tsx:179
  ...variantStyles[variant as keyof typeof variantStyles],      // Button.tsx:180
  if (message.type === 'audio_chunk_meta') { const meta = message as AudioChunkMetaMessage; // socketFrameParser.ts:132-133
  ```
- **Impact**: None today; removes the compiler's drift check between prop unions and style tables.
- **Suggested Fix**: Delete the casts (all compile as-is; verify with `type-check:prod`). Keep the three `MuiX as ComponentType<...>` styled() casts, which are genuine upcasts.

### D4-04: No `never`-based exhaustiveness anywhere; switches over closed unions fall through to a silent default
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `components/core/useConnectionStatus.ts:17-27,39-48`; `components/shared/Toast/toastColors.ts:12-22,32-42`; `components/library/Search/ResultAvatar.tsx:56-65`; `components/library/Controls/BatchActionsToolbar.tsx:46-56`; `components/shared/ConnectionStatusIndicator.tsx:50-60` (all under `auralis-web/frontend/src/`)
- **Status**: NEW
- **Description**: A repo-wide grep finds no `assertNever`, `satisfies never` or `: never` default (the only exhaustiveness check is the compile-time `_AssertExhaustive` in `types/ws/registry.ts`). Each switch above covers a closed union (`ConnectionStatus`, MUI `AlertColor`, `'track'|'album'|'artist'`, the position union) and ends in a plausible-looking default, so adding a union member silently renders it as "Disconnected" / the surface colour / the music-note icon. `getRemoveLabel(context: string)` additionally widens the prop's declared `'library'|'playlist'|'favorites'|'queue'` union to `string`, which discards narrowing before the switch even starts.
- **Evidence**:
  ```ts
  export const connectionStatusLabel = (status: ConnectionStatusType): string => {
    switch (status) { case 'connected': ... case 'connecting': ... case 'error': ... default: return 'Disconnected'; } };
  const getRemoveLabel = (context: string): string => {   // BatchActionsToolbar.tsx:46
  ```
- **Impact**: Latent only; a future fifth connection state (e.g. `reconnecting`) would be mislabelled with no compile error.
- **Suggested Fix**: Add a small `assertNever(x: never): never` in `utils/` and use it in the defaults (list `'disconnected'` explicitly in `connectionStatusLabel`); change `getRemoveLabel` to take `NonNullable<BatchActionsToolbarProps['context']>`.

### D4-06: Wire types declare non-null where the backend response model allows `null`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `utils/fingerprintToGradient.ts:14-41` (`AudioFingerprint`), `hooks/fingerprint/useTrackFingerprint.ts:34` (`track_title: string`), `services/settingsService.ts` `UserSettings.theme/language/output_device` (all under `auralis-web/frontend/src/`); backend `schemas/library.py:210-240`, `routers/fingerprint_status.py:56`, `routers/settings_models.py:135-136`
- **Status**: NEW
- **Description**: `FingerprintVectorResponse` declares all 25 dimensions `float | None`, `TrackFingerprintResponse.track_title` is `str | None`, and `SettingsResponse.theme/language/output_device` are `str | None`. The frontend types declare the 17 core fingerprint dimensions as required `number`, `track_title: string`, and `theme/language/output_device: string`. In practice the DB columns for the fingerprint are `nullable=False` and consumers use `?? 'default'` / `data?.track_title ?? null`, so nothing breaks today; but `getDominantFrequencyRegion` adds `fp.sub_bass + fp.bass + ...` directly, where a `null` would silently coerce to 0 and classify the album as 'bass'-dominant rather than failing.
- **Evidence**:
  ```py
  sub_bass: float | None = Field(default=None, ...)          # backend/schemas/library.py:210
  ```
  ```ts
  sub_bass: number;      // 20-60 Hz                            // fingerprintToGradient.ts:16
  ```
- **Impact**: Type claims stronger than the contract; low because the DB constraint holds.
- **Suggested Fix**: Either tighten the backend response model (drop `| None` on dimensions the DB guarantees) or widen the frontend types to `number | null` and let the compiler flag the unguarded arithmetic.

### D4-07: Dead global `Window` declarations in `types/window.d.ts`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/window.d.ts:9-21,35-37,43`
- **Status**: NEW
- **Description**: `__AURALIS_PERFORMANCE__` (`AuralisPerformanceInfo`), `__A11Y__` (`AuralisA11yInfo`) and `msCrypto` are declared on `Window`, but no file reads or writes them (grep of `src/` finds them only in the `.d.ts`; `src/performance/` was deleted in #4696). The file's own header says it exists to eliminate `(window as any)`, yet these declarations are the ones that would let a future `window.__A11Y__ = ...` compile unnoticed, and `AuralisPerformanceInfo`/`AuralisA11yInfo` are all-`unknown` shapes that document nothing.
- **Evidence**: `__AURALIS_PERFORMANCE__?: AuralisPerformanceInfo;  __A11Y__?: AuralisA11yInfo;  msCrypto?: Crypto;`
- **Impact**: Cosmetic; stale ambient declarations.
- **Suggested Fix**: Delete the three members and their two interfaces (keep `__AURALIS_DEBUG__`, `__auralisAnalyser`, `__auralisAudioContext`, which have consumers).

---
Notes (not findings): test code carries ~500 `any`/`as any` sites (concentrated in `test/mocks/handlers.ts`, `useEnhancementControl.test.ts`, `useLibraryQuery.test.ts`); they type-check and belong to Dim 9. `noUncheckedIndexedAccess` is deliberately off (measured 0 -> 146 production errors, tsconfig comment, closed #4665). ESLint is not installed (closed #4908), so the three `eslint-disable-next-line` comments in `useKeyboardShortcuts.ts:102`, `usePlayEnhanced.ts:217`, `useEnhancedStreamStart.ts:282` are inert.

### D5-02: `tokens.colors.accent.primary` used for text in ~15 live styles instead of `themeVars.accentText`
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `components/library/Styles/Tabs.styles.ts:32,54`; `components/library/Styles/Table.styles.ts:26,29`; `components/shared/MediaCard/MediaCardInfo.tsx:57`; `components/shared/DropZone/DropZoneText.tsx:23`; `components/shared/KeyboardShortcutsHelp.styles.ts:32,44`; `components/library/Styles/ArtistList.styles.ts:59`; `components/library/Details/ArtistDetailTabs.tsx:60`; `components/shared/ContextMenu/PlaylistSection.tsx:40`; `components/playlist/DroppablePlaylist.styles.ts:58`; `components/library/Items/artists/ArtistInfoModal.tsx:129`; `components/shared/SimilarTracksModal/SimilarTrackRow.tsx:70,106`
- **Status**: Regression of #5675 (acceptance criterion "Accent text on the light canvas meets 4.5:1" only wired into `TrackRow.styles.ts:124` and `TrackTableRowItem.tsx:86`)
- **Description**: `themeVars.accentText` exists precisely because brand `#7366F0` is 4.08:1 on the light canvas `#F8F9FD` (4.30:1 on white) while `lightMode.text.accent` `#5B4FD6` is 5.65:1. Only two files use it; the rest read the raw brand colour for labels (selected tab text, playing-track title, current-track number/title, shortcut keys, category titles, drop-zone title, hover artist name). Several sit on an accent tint (`opacityScale.accent.lighter`), lowering contrast further.
- **Evidence**:
```ts
// Tabs.styles.ts:31-33
'&.Mui-selected': { color: tokens.colors.accent.primary }
// MediaCardInfo.tsx:57
color: isPlaying ? tokens.colors.accent.primary : themeVars.textPrimary,
// TrackRow.styles.ts:124 (the only correct pattern)
color: iscurrent === 'true' ? themeVars.accentText : themeVars.textSecondary,
```
- **Impact**: Light-mode text slightly under AA (4.1-4.3:1 vs 4.5:1); icon/border uses of the same token are fine.
- **Suggested Fix**: Swap text-colour uses to `themeVars.accentText` (keep `tokens.colors.accent.primary` for fills, borders, icons). Add a source-scan guard for `color:\s*...tokens.colors.accent.primary`.

### D5-03: Seven design-system primitives still have zero consumers; #5132 was closed as "already resolved" but its five are still present
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `design-system/primitives/{Input,Badge,Checkbox,ProgressBar,Text,Box,Container}.tsx` (799 lines); barrels `design-system/primitives/index.ts:1-30`, `design-system/index.ts:17-31`
- **Status**: Regression of #5132 (closed 2026-11-17 with "1602e5009 dropped ... the five unused primitives"; that commit deleted `Modal/Stack/Toggle/Grid/LinearProgress` (#5217), not the five #5132 named)
- **Description**: No production file imports any of the seven (checked `from '@/design-system'` and `@/design-system/primitives/<Name>`); only `Container` is mentioned in a test string and `ProgressBar` collides by name with the unrelated live `components/player/ProgressBar`. `Input`, `Badge`, `Checkbox`, `ProgressBar`, `Text` are exactly the #5132 list; `Box` and `Container` are additional. Real UI uses `@mui/material` `Box`/`TextField`/`Chip` directly, so these primitives (and the `themeVars`/rgba migrations spent on them in #3981/#4877) are unverified by any render. The barrel doc `primitives/index.ts:3` says "18 core primitive components" but it exports 17, and `design-system/index.ts` re-exports only 15 (omits `ProgressBar`, `Checkbox`).
- **Evidence**:
```
$ git show --stat 1602e5009   # deletes Grid/Modal/Stack/Toggle/LinearProgress only
$ wc -l primitives/{Input,Badge,Checkbox,ProgressBar,Text,Box,Container}.tsx  -> still 199/108/65/108/110/161/47
```
- **Impact**: Maintenance/adoption only; contributors are told these are "the canonical components for all basic UI patterns" while the app routes around them.
- **Suggested Fix**: Delete the seven (and their barrel entries/README sections) or adopt them at the raw-MUI call sites; fix the "18" count. Reopen #5132.

### D5-04: ~65 unread leaf tokens remain after #6062 removed the unread groups
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `design-system/tokens/{colors,typography,layout,effects,surfaces,semantics}.ts`
- **Status**: NEW (adjacent to closed #6062, which removed whole groups only)
- **Description**: Per-leaf grep across `src/` (production AND tests, excluding `design-system/tokens/`) finds zero readers for the following, so the "single source of truth" contains a large dead surface that the token tests do not pin:
  - `colors.audioSemantic.{identityGlow,spatialGlow,stability,stabilityGlow,transient,transientGlow,harmonicGlow}`, `colors.text.tertiary`, `colors.opacityScale.white.{veryLight,standard,nearOpaque}`, `colors.utility.{disabledBg,errorHover,errorBgMedium,errorBorder,errorGlow}`
  - `typography.fontFamily.system`, `fontSize.{5xl,hero}`, `fontWeight.{light,extrabold}`, `letterSpacing.{normal,tight}`
  - `spacing.xxxxl`, `borderRadius.{none,2xl,3xl}`, `zIndex.{base,modalBackdrop,modal,popover,tooltip,debug}`
  - `shadows.{xs,base,glowStrong,glowAqua,glowAquaIntense,glowAquaUltra,glassSubtle,glassMd,glassStrong}`, `transitions.{verySlow,easeSmooth}`, `animations.{fadeIn,slideUp}`
  - `gradients.{aqua,borderSubtle}`, `gradients.decorative.{neonSunset,deepOcean,cosmicBlue}`, `glass.starfield.{subtle,soft,solid}`
  - `components.sidebar.collapsedWidth`, `components.rightPanel.minWidth`, `components.albumCard.{size,hoverShadow}`, `components.albumCover.*`, `components.button.{primary,icon}.*`, `components.searchBar.{background,borderRadius}` (and several playerBar/sidebar/rightPanel `zIndex/backdropFilter/border*/shadow` members, each read nowhere)
- **Evidence**: e.g. `grep -rn "glowAquaUltra\|glassStrong\|albumCover\|collapsedWidth" src | grep -v design-system/tokens/` returns nothing.
- **Impact**: Dead design values read as supported API, can drift from live ones, and invite re-adding hard-coded copies elsewhere. Per the dimension checklist, a token with no consumer is a finding.
- **Suggested Fix**: Delete the unread leaves (or wire a real consumer) and add a "no unread token" scan to `design-system/__tests__` modelled on `spacingTokens.test.ts`.

### D5-05: `borderRadius` reads the spacing scale (6 sites); radius guard only matches string literals
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `components/library/Styles/Grid.styles.ts:19`; `components/library/Styles/SearchStyles.styles.ts:71,80`; `components/library/Styles/ArtistDetail.styles.ts:25`; `components/playlist/DroppablePlaylist.styles.ts:10,52`
- **Status**: NEW
- **Description**: Radii are taken from `tokens.spacing.*` (xs=4px, sm=6px, md=12px) instead of `tokens.borderRadius.*` (sm=8px "minimum for any rounded element", md=12px). The values therefore move with the spacing scale, and 4px/6px sit below the documented radius floor. `spacing.md` (12px) is exactly `borderRadius.md`. The #5648 guard (`/borderRadius:\s*['"](8|12|16)px['"]/`) cannot see token-category mix-ups.
- **Evidence**:
```ts
// Grid.styles.ts:19         borderRadius: tokens.spacing.md,
// SearchStyles.styles.ts:80 borderRadius: tokens.spacing.xs,
// DroppablePlaylist.styles.ts:10 borderRadius: tokens.spacing.xs,
```
- **Impact**: Cosmetic/maintainability; retuning spacing silently changes corner radii.
- **Suggested Fix**: Use `tokens.borderRadius.md` for the 12px case and `tokens.borderRadius.sm` (or a documented literal like the other 2-6px radii recorded in #5648) for the rest; add `borderRadius:\s*tokens\.spacing` to the spacing guard.

### D5-06: Letter-spacing tokens bypassed: 26 literal sites, 3 exactly equal a token
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `components/library/Details/DetailViewHeader.tsx:104` (`'-0.01em'` = `letterSpacing.tight`, comment even says "Tight tracking"); `components/library/Details/ArtistHeader.tsx:81` and `components/library/Views/AlbumsTab.tsx:82` (`'0.02em'` = `letterSpacing.loose`); remaining literals e.g. `LibraryHeader.tsx:36`, `ViewContainer.tsx:70`, `ArtistList.styles.ts:88,100,123`, `SidebarStyles.ts:41`, `PlaylistSection.tsx:59`, `EnhancementToggleStyles.ts:49`
- **Status**: NEW
- **Description**: `typography.letterSpacing` defines `normal/tight/loose`, but only two files read it (`ThemeToggle.styles.ts:54`, `Typography.styles.ts:55`). The #5648 "values equal to a token use the token" guard covers radius/line-height/pulse but not letter-spacing, so exact matches persist.
- **Evidence**: `letterSpacing: '-0.01em',  // Tight tracking for headers` (DetailViewHeader.tsx:104) while `tokens.typography.letterSpacing.tight === '-0.01em'`.
- **Impact**: Minor drift risk; two token steps are dead (D5-04) while their values are re-typed.
- **Suggested Fix**: Use the token for the three exact matches; add `letterSpacing:\s*['"](-0\.01em|0\.02em)['"]` to the #5648 guard; decide whether the off-scale values (0.05em, 0.5px, 1px...) warrant new steps.

### D5-07: Template-literal spacing values equal to a token slip past the `(padding|margin|gap): '` guard
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `components/shared/KeyboardShortcutsHelp.styles.ts:28` (`padding: \`${tokens.spacing.sm} 12px\``, 12px = `spacing.md`); `components/library/Styles/SearchStyles.styles.ts:81` (`margin: \`2px ${tokens.spacing.xs}\``, 2px = `spacing.xxs`)
- **Status**: NEW
- **Description**: `spacingTokens.test.ts` source-scans only `(padding|margin|gap): '` (single-quoted). Backtick values mixing a token with a literal that equals another step are unguarded. (Other template literals, `PlaylistSection.tsx:29,43` `48px` and `ErrorBoundary.tsx:131` `10px 24px`, are documented off-scale exceptions and are fine.)
- **Evidence**: see Location.
- **Impact**: Trivial; listed for guard completeness.
- **Suggested Fix**: Replace with `tokens.spacing.md` / `tokens.spacing.xxs`; extend the guard regex to template literals.

---
Orphaned-component notes (no separate finding; covered by OPEN #5628): `library/Search/*` `TypeChip` (`SearchStyles.styles.ts:98-110`) paints `accent.secondary`/`accent.tertiary` text on an accent tint, about 1.2:1 in light mode; `ConnectionStatusIndicator`/`ConnectionDetailsPanel`/`ProcessingToast` use dark `semantic.*` text. Fix or delete together with the orphan decision.

### D6-04: Nine call sites re-check the abort signal instead of trusting the transport; the comments justifying it are wrong
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `hooks/library/useLibraryStats.ts:55`, `hooks/library/useLibraryScan.ts:160`, `hooks/enhancement/useEnhancedPlayCommand.ts:89`, `hooks/fingerprint/useSimilarTracks.ts:232`, `components/library/EditMetadataDialog/useMetadataForm.ts:108,188`, `components/library/Details/usePlaylistDetails.ts:35`, `useArtistDetailsData.ts:92`, `useAlbumDetails.ts:101`; abort-by-signal-only in `hooks/library/useLibraryPagination.ts:89-94`, `hooks/library/libraryPageFetch.ts:86-90`
- **Status**: NEW
- **Description**: The contract (#5653) is that `apiRequest` rethrows a caller abort as a raw `AbortError`, tested with `isAbortError`. These sites still write `if (controller.signal.aborted || isAbortError(err)) return;`. The comments say the opposite of the contract. `usePlaylistDetails.ts:34` says "the signal is authoritative regardless of how the transport shapes an abort". `useMetadataForm.ts:187` says "the shared transport rewraps aborts". `useLibraryPagination.ts:81` and `libraryPageFetch.ts:87` say "`get()` does not preserve the original error's type/name". All of these are false. `useLibraryPagination.runGuarded` and `libraryPageFetch.replaceAbortController` rely only on the signal and never call `isAbortError`. This is the exact pattern the checklist calls out ("re-checks the signal because it distrusts this"). One genuine residual case exists: `apiRequest`'s non-2xx branch calls `readHttpErrorBody`, which swallows an abort during the body read, so a cancelled request can surface as an `APIRequestError` with a status. That residual is the reason the re-check cannot be removed today.
- **Evidence**:
```ts
// usePlaylistDetails.ts:33-35
// Same abort semantics as useAlbumDetails (#3601/#4643): the signal
// is authoritative regardless of how the transport shapes an abort.
if (controller.signal.aborted || isAbortError(err)) return;
// libraryPageFetch.ts:86-88  "get() does not preserve the original error's type/name, so abort detection reads the controller's own signal"
```
- **Impact**: Maintainers are told the transport is untrustworthy, which invites more per-site handling and hides the one real transport gap. No user-visible defect today.
- **Suggested Fix**: In `apiRequest`'s error branch, rethrow the abort when `signal?.aborted` before building the `APIRequestError`. Then collapse these sites to `isAbortError(err)` (a shared helper if desired). Correct the false comments.

### D6-05: User-facing failure text drops the backend's reason (bypasses failureMessage)
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `components/library/useBatchOperations.ts:30-41,93,114,119,142,171`; `components/playlist/usePlaylistContextActions.ts:56-58`; `hooks/library/libraryPageFetch.ts:77-81` (`friendlyFetchError`), used by `hooks/library/useLibraryPagination.ts:101-103`; `hooks/app/useAppDragDrop.ts:81,111-124`; reason-only variants in `components/library/Items/artists/useContextMenuActions.ts:49,81,100` (`err instanceof Error ? err.message : '...'`)
- **Status**: NEW (sibling of closed #5652, whose `failureMessage` sweep missed these)
- **Description**: These paths catch an `APIRequestError` carrying the backend's `detail` and show a fixed literal instead of `failureMessage(prefix, err)`.
  - `useBatchOperations`: bare `catch { error('Failed to add tracks to queue') }`, `Failed to add tracks to "<playlist>"` (twice), and `reportBatchResult`'s fixed `failMsg` for the all-rejected `Promise.allSettled` case.
  - `usePlaylistContextActions`: `Failed to play playlist "<name>"`.
  - `friendlyFetchError`: a server-side failure maps to a fixed string such as "Failed to load library", dropping the detail (for example a 503 "library unavailable").
  - `useAppDragDrop`: `withFallbackMessage` re-implements the logic and then shows the error through the `info` toast (informational severity) with no prefix.
  - `useContextMenuActions`: shows the bare reason without a prefix.
- **Evidence**:
```ts
// useBatchOperations.ts:91-95
try { result = await addTracksToQueue(trackIds); } catch { error('Failed to add tracks to queue'); return; }
// usePlaylistContextActions.ts:56-58
console.error('Failed to play playlist:', err);
errorToast(`Failed to play playlist "${playlist.name}"`);
```
- **Impact**: A 503, a 404 for a deleted playlist or a timeout all read the same. The checklist names this exact pattern as a finding.
- **Suggested Fix**: Use `failureMessage('Failed to add tracks to queue', err)` and the equivalent at each site. For the batch results, take the first rejected reason. Make `friendlyFetchError` return `failureMessage(serverFailureMessage, err)` for non-zero statuses. Show drag-drop failures with the error toast, not `info`.

### D6-06: GET call sites that consume fields directly with no `validate` guard (one guard defined but unused)
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `hooks/enhancement/useEnhancementStatusSync.ts:36-38,121-128`, `hooks/library/useFingerprintCoverage.ts:93-97,127-132`, `hooks/fingerprint/useAlbumFingerprint.ts:54-55`, `hooks/enhancement/useEnhancedPlayCommand.ts:81`, `components/library/EditMetadataDialog/useMetadataForm.ts:89-103`; unused guard `services/api/cacheShapeGuards.ts:92` (`isCacheHealthShape`)
- **Status**: NEW
- **Description**: These calls only assert the type, and their consumers read the fields directly.
  - Enhancement status: `response.enabled/preset/intensity` are written straight into hook state. A drifted body yields `undefined` state instead of a located failure.
  - Fingerprint coverage: `toCoverage(raw)` reads `raw.pending_tracks` and so on. A missing field makes `pendingTracks` `undefined`, so the `pendingTracks === 0` poll-stop test (line 130) never passes and the 10 s poll runs forever.
  - Single-album fingerprint: `data.fingerprint` is unguarded, while the track-fingerprint sibling and the batch sibling both have guards (#6063).
  - `loadCurrentTrack`: `transformTrack(await get<TrackApiResponse>(...))`.
  - `useMetadataForm`: hand-rolls an inline shape check instead of a `responseGuards` guard.
  - Separately, `isCacheHealthShape` has zero production callers. Nothing fetches `/api/cache/health`, and `setCacheHealth` has no dispatcher. A guard that exists but is unused implies coverage that is not there.
- **Evidence**:
```ts
const raw = await get<RawCoverage>('/api/library/fingerprints/status', { signal: abortRef.current.signal }); // no validate
setCoverage(toCoverage(raw));
```
- **Impact**: Backend field drift surfaces far from its cause, and the exact class of bug (#3593, #3976, #4440) that `validate` was introduced for. One drift case makes polling endless.
- **Suggested Fix**: Add guards for these shapes to `api/responseGuards.ts` and pass `validate:`. Delete `isCacheHealthShape` or wire it to a real consumer.
- **Cross-dimension note**: Also found by Dimension 4 as D4-05 (the same eight REST reads that lack a `validate` guard after #6063).

### D6-07: Call-site retry rules that bypass `shouldRetryQuery`
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `hooks/fingerprint/useAlbumFingerprint.ts:95,231`; `hooks/fingerprint/useTrackFingerprint.ts:27,138`
- **Status**: NEW
- **Description**: Both album-fingerprint hooks set `retry: false`, justified as "retrying a failing endpoint once per visible album is not worth the request volume". That rationale was overtaken by #5873. `useAlbumFingerprints` now coalesces a page of tiles into one `/api/albums/fingerprints` request, so a retry costs one request per page, not one per tile. The sibling `useTrackFingerprint` was converged on the app-wide policy in #6064 ("No retry override"). The track hook also keeps a second transient-status classification, `TRANSIENT_OUTAGE_STATUSES = {0,408,429,502,503,504}`, beside `isRetryableStatus` in `utils/queryRetry.ts`. The two differ on 500 and other 5xx, and a rule change has to be made in two places.
- **Evidence**:
```ts
retry: false,   // useAlbumFingerprint.ts:95 and :231
const TRANSIENT_OUTAGE_STATUSES: ReadonlySet<number> = new Set([0, 408, 429, 502, 503, 504]); // useTrackFingerprint.ts:27
```
- **Impact**: A transient 503 on the batch endpoint leaves a whole page of album tiles on the hash gradient until the next mount or refetch. The status rule is duplicated.
- **Suggested Fix**: Drop `retry: false` so the global `shouldRetryQuery` applies. Export `isRetryableStatus` from `queryRetry.ts` and reuse it (or a named subset) in the track hook.

### D6-08: Re-typed pagination and timeout literals (config/api.ts and timing.ts constants bypassed)
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `components/library/Items/albums/CozyAlbumGrid.tsx:88` (`limit: 50`), `components/library/Items/artists/CozyArtistList.tsx:62` (`limit: 50`), `components/library/Hooks/useSearchLogic.ts:108,112,116` (`&limit=5`), `hooks/library/useLibraryScan.ts:113` (`timeoutMs: 5_000`)
- **Status**: NEW
- **Description**: #6217 introduced `LIBRARY_PAGE_LIMIT` because the page size "was hand-typed in six places". Two call sites in the library components still pass the literal `50`. The search dropdown hardcodes `limit=5`. The scan-folder registration call has an unnamed 5 s timeout, while the checklist wants timeouts to come from named constants.
- **Evidence**:
```ts
} = useInfiniteAlbums({ limit: 50, search, ...SERVER_ORDER[sortBy] });
} = useArtistsQuery({ limit: 50, search });
{ signal: controller.signal, timeoutMs: 5_000 }
```
- **Impact**: Changing the page size or timeout policy no longer takes effect everywhere. Low runtime risk.
- **Suggested Fix**: Use `LIBRARY_PAGE_LIMIT`, and add `SEARCH_RESULT_LIMIT` and `SETTINGS_REGISTRATION_TIMEOUT_MS` constants (or equivalent) in `config/`.

### D6-09: Base-URL handling gaps in config/api.ts and artworkService
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `config/api.ts:38,63-67`; `services/artworkService.ts:34-36,56-58`; `utils/apiRequest.ts:44-52,129`
- **Status**: NEW
- **Description**:
  1. `getApiUrl` only normalises the leading slash of the path, not a trailing slash on `API_BASE_URL`. `VITE_API_URL=http://localhost:8765/` yields `http://localhost:8765//api/...`. `wsBaseFromApiBase` does strip trailing slashes, so the two transports disagree for the same variable.
  2. `getArtworkUrl` honours `API_BASE_URL`, but `withArtworkSize` returns backend-provided relative `/api/albums/..../artwork` URLs (track and album `artworkUrl`) unchanged. With an absolute `VITE_API_URL` the REST calls go to the override host while `<img src>` resolves against the page origin.
  3. The `buildUrl` docblock says it is "the single URL builder for both apiRequest's `params` option and useRestAPI's queryParams". `apiRequest` has no `params` option and does not call `buildUrl`. It uses `getApiUrl` directly and so lacks `buildUrl`'s absolute-URL passthrough. There are two URL joiners with slightly different behaviour.
- **Evidence**:
```ts
export function getApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;     // trailing '/' on API_BASE_URL -> '//api'
}
```
- **Impact**: Only matters when `VITE_API_URL` is set, which is the documented override (#4468) and not the default path. Artwork then breaks against a cross-origin backend.
- **Suggested Fix**: Strip trailing slashes from `API_BASE_URL` once at definition. Prefix backend-provided `/api/` artwork URLs with `API_BASE_URL` in `withArtworkSize`. Have `apiRequest` use `buildUrl`, and fix the docblock.

### D6-10: Health poll: 30 s timeout at a 5 s interval with no overlap guard and no unmount abort
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `hooks/shared/useAPIHealthPoll.ts:19-47`
- **Status**: NEW
- **Description**: `get('/api/health')` uses the default `DEFAULT_TIMEOUT_MS` (30 s) while the interval is 5 s, and there is no in-flight guard and no `AbortSignal`. A backend that accepts the connection but stalls leaves up to six polls pending. The "disconnected" indicator is delayed by the full 30 s. The unmount cleanup sets `mountedRef.current = false` but cancels nothing. The comment at line 31 claims the fix prevents accumulating hung requests, but it only bounds them.
- **Evidence**:
```ts
const health = await get<{ auralis_available?: boolean } | null>('/api/health'); // no signal, no timeoutMs
intervalRef.current = setInterval(pollHealth, intervalMs);                       // no in-flight check
```
- **Impact**: Slow failure detection for the connection indicator in a stalled-backend state. Resource overhead is negligible.
- **Suggested Fix**: Pass `timeoutMs: intervalMs` and an `AbortController` aborted in cleanup, and skip a tick while a poll is in flight.

### D6-11: Settings dialog Reset / Add folder / Remove folder expose no in-flight state; settings load has no cancellation or stale guard
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `components/settings/useSettingsDialog.ts:33-47,89-153`, `components/settings/SettingsDialogFooter.tsx:27`
- **Status**: NEW
- **Description**: Only `handleSave` toggles `isSaving`. `handleReset`, `handleAddScanFolder` and `handleConfirmRemove` run async POSTs with no loading or disabled state, and the Reset button is disabled only by `isSaving`, which Reset never sets. A double click sends two reset requests. `loadSettings` passes no signal and has no latest-request guard. Closing and reopening the dialog quickly can start two overlapping loads, and an older response that resolves last overwrites the newer settings.
- **Evidence**:
```tsx
<Button onClick={onReset} startIcon={<ResetIcon />} variant="danger" disabled={isSaving}>
const handleReset = useCallback(async () => { setError(null); try { const result = await settingsService.resetSettings(); ...
```
- **Impact**: Duplicate requests and a rare stale-settings overwrite. Both are low frequency.
- **Suggested Fix**: Add a shared `busy` state (or a ref guard) around the three mutations and bind it to the buttons. Use `useLatestRequestGuard` (already in the codebase) or an AbortController in `loadSettings`.

### D7-03: The "Show visualizations" switch does not stop the AlbumCharacterPane's perpetual animations
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/WaveformVisualization.tsx:87-90`, `.../GlowingArc.tsx:55,79`, `.../CharacterTags.tsx:68`, `.../EnergyField.tsx:104`, `.../FloatingParticles.tsx:54`, `.../animations.ts:35-67`, `auralis-web/frontend/src/App.tsx:53-59`, `auralis-web/frontend/src/components/settings/InterfaceSettingsPanel.tsx:63-73`
- **Status**: NEW (related to closed #5676, which wired the switch only to the starfield)
- **Description**: While audio plays, `isAnimating` is true and the pane runs `infinite` CSS animations. These include `arcPulse` (animates `filter: blur`) on two stacked layers, `barGlow` (animates `filter: drop-shadow`) plus `breathePulse` on seven bars, `subtleGlow` (animates `box-shadow`, which is not compositor-animatable) on up to five chips, and 15 `particleFloat` elements that each carry a `box-shadow` glow. The only user opt-out for visual cost is the Settings switch "Show visualizations: Display audio visualizations and waveforms". It is consumed in `App.tsx` solely to mount or unmount `StarfieldBackground`. The pane's waveform and particle visuals, the literal "visualizations and waveforms", stay on, and none of its components read the setting. `RotatingDescription` is the only part of the pane that reads `usePrefersReducedMotion`. The other animations rely on the global CSS reduced-motion override.
- **Evidence**:
```tsx
// App.tsx:53-59
const showVisualizations = useShowVisualizations();
{showVisualizations && <StarfieldBackground className="app-ambient-background" />}
// AlbumCharacterPane.tsx / children: no use of useShowVisualizations; animations run whenever isAnimating
```
```ts
// animations.ts
export const barGlow = keyframes` ... filter: drop-shadow(0 0 4px ...) ... drop-shadow(0 0 12px ...) `;
export const subtleGlow = keyframes` ... box-shadow: 0 0 8px 2px ... 0 0 16px 4px ... `;
```
- **Impact**: A user on a weak GPU or integrated graphics who turns visualizations off to save power still gets continuous blur, drop-shadow and box-shadow animation on the right-hand pane for the whole listening session, on top of the main-thread render work in D7-02. Not measured. The `filter` animations may be compositor-driven, but the `box-shadow` ones repaint on the main thread.
- **Suggested Fix**: Read `useShowVisualizations()` (or lift it into the pane via a prop or context) and pass `isAnimating = isAnimating && showVisualizations` to the five children, or skip `FloatingParticles` and `WaveformVisualization` entirely. Prefer opacity and transform keyframes over `box-shadow` for the chip glow. Add `will-change` only where profiling shows a benefit.

---

### D8-07: Virtualized artist list and album grids expose no total size/position (and the artist list no list semantics)
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `components/library/Items/artists/ArtistListContent.tsx:155-200`, `components/library/Items/albums/VirtualizedAlbumGrid.tsx:125,156`, `components/library/Items/albums/EraSection.tsx:103`
- **Status**: Regression of #5672 (closed; its scope named the artist list but only the track listbox and queue got `aria-setsize/posinset`)
- **Description**: `grep -rn "aria-setsize\|aria-posinset" src` matches only TrackRow and QueueTrackItem. The artist list renders only the virtual window as plain `<div>`s of buttons (no `role="list"`/`listitem`, no setsize), and the Albums grid wraps each card in `role="listitem"` inside `role="list" aria-label="Albums"` but without `aria-setsize`/`aria-posinset`, so AT reports the mounted window (a few dozen cards) as the whole list.
- **Evidence**:
  ```tsx
  // VirtualizedAlbumGrid.tsx:125
  <div role="listitem" key={album.id}>   // no aria-setsize / aria-posinset
  ```
- **Impact**: Screen-reader users cannot judge collection size or position in Albums/Artists (WCAG 1.3.1).
- **Suggested Fix**: Pass total count into the grid/list and set `aria-setsize`/`aria-posinset={index+1}` on each item; give ArtistListContent `role="list"` + `listitem` wrappers (alphabet headers as `role="presentation"` or group labels).

### D8-08: Album artwork alt text exposes the database id ("Album 42 artwork") and duplicates the heading
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `components/album/AlbumArt.tsx:104,112,129`; consumer `components/library/Details/AlbumHeaderActions.tsx:70-74`
- **Status**: NEW
- **Description**: `AlbumArt` has only `albumId`, so its image alt (and the button aria-label when clickable) is `Album ${albumId} artwork`. On the album detail header, which is directly next to the album's `<h1>`, a screen reader announces "Album 42 artwork", an internal id that means nothing to the user, instead of treating the cover as decorative or naming the album.
- **Evidence**:
  ```tsx
  const artworkLabel = albumId ? `Album ${albumId} artwork` : 'Album artwork';
  ...  alt={artworkLabel}
  ```
- **Impact**: Noise/confusing announcement on every album detail view (WCAG 1.1.1 / 2.4.6 quality).
- **Suggested Fix**: Add an optional `alt`/`title` prop; AlbumHeaderActions passes `alt=""` (title is rendered adjacent) and clickable usages pass the album title.

### D8-09: Toggle buttons set aria-pressed and also flip their accessible name
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `components/player/VolumeControl.tsx:121-128`, `components/library/Details/AlbumActionButtons.tsx:78-84`
- **Status**: NEW (the mute `aria-pressed` was added deliberately in #6072; this concerns pairing it with a changing label)
- **Description**: WAI-ARIA APG toggle-button guidance: do not change the label when the state is conveyed by `aria-pressed`. The mute button announces "Unmute, toggle button, pressed" when muted (and "Unmute, not pressed" when volume is 0 but not muted), and the favourite button announces "Album is favorited. Press to remove, toggle button, pressed". The state is stated twice and the two can read as contradictory.
- **Evidence**:
  ```tsx
  const muteLabel = isMuted || clampedVolume === 0 ? 'Unmute' : 'Mute';
  <button aria-label={muteLabel} aria-pressed={isMuted} ...>
  <IconButton aria-pressed={isFavorite} aria-label={isFavorite ? 'Album is favorited. Press to remove' : 'Album is not favorited. Press to add'}>
  ```
- **Impact**: Ambiguous state announcement for screen-reader users.
- **Suggested Fix**: Use a constant name ("Mute", "Favorite") with `aria-pressed`, or keep the action-label and drop `aria-pressed`. Keep the tooltip text action-oriented.

### D8-10: Album/artist track table has an unlabeled fifth column and an empty-row colSpan of 4
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `components/library/Items/tables/TrackTableHeader.tsx:20-62`, `components/library/Items/tables/TrackTableRowItem.tsx:109-125`, `components/library/Items/tables/AlbumTrackTable.tsx:68`
- **Status**: NEW
- **Description**: The header defines four `<th>`-equivalent cells (#, Title, Artist, Duration) but each row renders five cells (the trailing "More options" button cell has no header), so the last column has no column header for table navigation, and the "No tracks found" row uses `colSpan={4}`. Related: rows are `<tr tabIndex=0 aria-label="Play …">` with no role/affordance beyond the label (the #3931 fix), so activation is conveyed only by the name.
- **Evidence**:
  ```tsx
  // TrackTableRowItem.tsx:109  <TableCell align="right" onClick={(e) => e.stopPropagation()}> <IconButton aria-label=`More options for ...`>
  // TrackTableHeader.tsx — 4 TableCell children only
  ```
- **Impact**: Minor: table-navigation users hear no header for the actions column.
- **Suggested Fix**: Add a fifth header cell containing a visually hidden "Actions" label and set `colSpan={5}`.

### D9-01: Test-quality gates only scan `*.test.ts(x)` and skip `it.each` bodies
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/scripts/check-weak-tests.mjs:43,52-60`; `auralis-web/frontend/src/tests/vi-mock-targets-exist.test.ts:27`; `auralis-web/frontend/src/tests/integration-tests-exercise-production-code.test.ts` (spec collection); `auralis-web/frontend/src/components/__tests__/a11y.spec.tsx`
- **Status**: NEW
- **Description**: Three meta-guards (the weak-test ratchet #5682, the `vi.mock` target guard #5678, the integration-spec guard #5119) are the suite's only protection against vacuous specs and no-op mocks. Each decides what to scan with a `.test.` filename regex, but `vitest.config.ts` includes `src/**/*.{test,spec}.{ts,tsx}`. `src/components/__tests__/a11y.spec.tsx` (265 lines, 20 tests, run in CI) is the one spec named `.spec.`, so it is invisible to all of them. Separately, `check-weak-tests.mjs` `asTestCall()` only recognises `it(...)`, `it.skip/only/concurrent(...)` where the callee is an identifier or property access. An `it.each([...])('title', fn)` call has a CallExpression as callee, so `root` is not an Identifier and it returns `null`. The 44 `it.each`/`test.each` specs in the tree are never classified, so a zero-assertion or presence-only parameterised test would pass the gate. A scratch scan that applies the same classifier to the 44 each-bodies finds 0 offenders today, so this is a latent gap, not a live defect. The gap would let a future stale `vi.mock` target in `a11y.spec.tsx` (it mocks `usePlayEnhanced` and `usePlaybackQueue`) silently mock nothing.
- **Evidence**:
  ```js
  // check-weak-tests.mjs:43
  } else if (/\.test\.(ts|tsx)$/.test(name)) {
  // check-weak-tests.mjs:52-56 -- callee of it.each(x)(...) is a CallExpression
  const root = ts.isPropertyAccessExpression(callee) ? callee.expression : callee;
  if (!ts.isIdentifier(root) || !TEST_CALLEES.has(root.text)) return null;
  // vi-mock-targets-exist.test.ts:27
  } else if (/\.test\.tsx?$/.test(entry)) {
  ```
- **Impact**: Three ratchets silently exempt a whole class of specs; a regression in those specs would not fail `frontend-test.yml`.
- **Suggested Fix**: Use `/\.(test|spec)\.tsx?$/` in all three collectors (or rename `a11y.spec.tsx` to `a11y.test.tsx`). In `asTestCall` also unwrap `it.each(...)` / `test.each(...)` call-expression callees (and add a case to `check-weak-tests.test.mjs`).

### D9-02: CozyAlbumGrid sort modes and the Era-grouped render path are never exercised
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:46-50,99-103,144`; `.../albums/EraGroupedAlbums.tsx`; `.../albums/EraSection.tsx` (197 lines); `.../Views/LibraryViewRouter.tsx:33,138,207`
- **Status**: NEW
- **Description**: The Albums view exposes an A-Z / Year / Era selector (`LibraryViewRouter` `sortBy` state, passed to `CozyAlbumGrid`). Era mode renders a structurally different tree (`EraGroupedAlbums` -> `EraSection`, with `useLayoutEffect` scroll-element lookup and `useGridVirtualizer`). No spec ever passes `sortBy` (grep of all specs for `sortBy`/`'era'` outside queue code returns nothing), so `EraGroupedAlbums`, `EraSection` and the `SERVER_ORDER` mapping (`az`->title/asc, `year`/`era`->year/desc, #5868) have no render or request-shape test. `CozyAlbumGrid.test.tsx` (699 lines) and `CozyAlbumGrid.loadMoreError.test.tsx` only run the default `az` path. `useInfiniteAlbums.test.ts` pins `order_by` for the hook, but not the grid's mapping from sort mode to hook arguments. `LibraryViewRouter` is only touched by `singleH1PerView` and the integration spec.
- **Evidence**:
  ```ts
  // CozyAlbumGrid.tsx:46-50
  const SERVER_ORDER: Record<AlbumSortOption, {...}> = {
    az: { orderBy: 'title', order: 'asc' },
    year: { orderBy: 'year', order: 'desc' },
    era: { orderBy: 'year', order: 'desc' },
  };
  // :144
  {sortBy === 'era' ? (<EraGroupedAlbums eraGroups={eraGroups} ... />
  ```
- **Impact**: A regression in era grouping (empty groups, duplicate albums across pages, virtualization fallback) or in sort-to-request mapping ships unseen.
- **Suggested Fix**: Add a CozyAlbumGrid spec that renders with `sortBy='year'` and `sortBy='era'`, asserts the `order_by`/`order` query params, that era headers render with the grouped albums, and that a second page keeps group membership.

### D9-03: Settings scan-folder add / remove-confirm flow has no behavioural test
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:105-158`; `auralis-web/frontend/src/components/settings/FoldersList.tsx`; also `AutoScanSettings.tsx`, `LibrarySettingsPanel.tsx`, `PlaybackSettingsPanel.tsx`
- **Status**: NEW
- **Description**: `useSettingsDialog.test.ts` covers cancel-reset, save vs reset notifications and Scan Now errors. The folder flow is untested: `handleAddScanFolder` (Electron `selectFolder` picker, cancel -> silent bail, picker throws -> logged and bail, success -> `setSettings` + `onSettingsChange`, failure -> `setError`), `handleRemoveScanFolder` (opens confirm), `handleConfirmRemove` (clears confirm state before the request, updates settings, error path) and `handleCancelRemove`. `FoldersList` is only passed `vi.fn()` props in `SettingsDialog.test.tsx` and named in `TextDisabledContrast.test.ts`. `settingsService.test.ts` covers the REST calls, but `useSettingsDialog.test.ts` mocks `addScanFolder`/`removeScanFolder` as bare `vi.fn()` that no test calls. `LibrarySettingsPanel` and `PlaybackSettingsPanel` are never referenced by any spec; `AutoScanSettings`, `AudioSettingsPanel` and `EnhancementSettingsPanel` are only checked for accessible names (`settingsAccessibleNames.test.tsx`), not for edit-to-pending-change behaviour. Remove is a destructive library action guarded by a confirm dialog.
- **Evidence**:
  ```ts
  // useSettingsDialog.ts:141-154
  const handleConfirmRemove = useCallback(async () => {
    if (!removeConfirmFolder) return;
    const folder = removeConfirmFolder;
    setRemoveConfirmFolder(null);
    ...
      const result = await settingsService.removeScanFolder(folder);
  ```
  Grep of all specs for `handleAddScanFolder|handleConfirmRemove|handleRemoveScanFolder` returns no match.
- **Impact**: The confirm-then-remove contract and the Electron picker fallbacks can regress without a failing spec.
- **Suggested Fix**: Add `useSettingsDialog` cases for picker success/cancel/throw, add failure, remove-confirm/cancel/failure, plus one `SettingsDialog` interaction spec that clicks Remove, confirms, and asserts `removeScanFolder` was called with that folder.

### D9-04: EditPlaylistDialog and its form hook have zero tests
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/playlist/EditPlaylistDialog.tsx`; `.../playlist/useEditPlaylistForm.ts:1-85`; `.../playlist/PlaylistFormFields.tsx`
- **Status**: NEW
- **Description**: Renaming/editing a playlist is a live user flow (the dialog is reachable from the app; it is not in the orphan list). No spec references `EditPlaylistDialog`, `useEditPlaylistForm` or `PlaylistFormFields`. Untested behaviour: the form seeds from `playlist` via an effect, the empty-name guard (`error('Please enter a playlist name')`), trimmed name/description payload to `updatePlaylist`, success toast then `onPlaylistUpdated` then `onClose`, failure toast, `handleClose` blocked while `loading`, and Enter-to-save. The create path has coverage only through `tests/integration/library-management/playlist-management.test.tsx`, and `useCreatePlaylistForm` has no spec of its own.
- **Evidence**:
  ```ts
  // useEditPlaylistForm.ts:26-34
  const handleSave = useCallback(async () => {
    if (!playlist) return;
    if (!name.trim()) { error('Please enter a playlist name'); return; }
    setLoading(true);
  ```
  `grep -lw EditPlaylistDialog $(all specs)` -> empty.
- **Impact**: Regressions in playlist rename (blank-name guard, payload trimming, close-while-saving) would not be caught.
- **Suggested Fix**: Add `useEditPlaylistForm.test.ts` (renderHook with mocked `playlistService.updatePlaylist` and Toast) and a small dialog render spec.


## Existing Issues Confirmed (not re-reported, 4)

### D1-07: Orphaned components and hooks remain (the 200+ line ones included)
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `components/shared/ConnectionDetailsPanel.tsx` (261), `ConnectionStatusIndicator.tsx` (181), `components/library/SearchBar.tsx` (242), `components/library/Hooks/useSearchLogic.ts` (193), `components/library/Search/*`, `components/navigation/SearchBar.tsx`, `components/track/TrackCard{Info,Overlay,Helpers,Styles}`, `hooks/shared/useAPIHealthPoll.ts` (90), `hooks/shared/useAutoHide.ts` (25) and others
- **Status**: Existing: #5628 (open); the connection-slice side is Existing: #5615 (open)
- **Description**: A reachability walk from `index.tsx` (static and dynamic imports, barrels over-approximated as reachable) leaves 27 non-test files, 2,638 lines, unreachable. That is the #5628 set minus the queue-extras clusters deleted since, plus two hooks: `useAPIHealthPoll` (named in #5615, whose results nothing consumes) and `useAutoHide` (only its test imports it). Their size inflates the 100+ line function census above (`ConnectionDetailsPanel` 236, `useSearchLogic` 145) and keeps a second `SearchBar` implementation alive next to the live top-bar one.
- **Evidence**: reachability scan output, for example `components/shared/ConnectionDetailsPanel.tsx 261`, `hooks/shared/useAutoHide.ts 25` (importers: only `__tests__/useAutoHide.test.ts`).
- **Impact**: Dead UI is still edited and audited; no runtime effect.
- **Suggested Fix**: Resolve per #5628 (delete or mount), and add `useAutoHide` / `useAPIHealthPoll` to that decision.

---

### D2-06: Write-only player state and backend-fed `isPlaying`
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `store/slices/playerSlice.ts` (`currentTime`, `duration`, `preset`, `lastUpdated`), `store/slices/cacheSlice.ts`, `hooks/player/playerStateSnapshot.ts:57,87-96`
- **Status**: Existing: #6039 (write-only state), #6015 (local session never writes `isPlaying`; also gates the 10 Hz tick in `usePlaybackTransport.ts:128`)
- **Description**: Re-verified at HEAD: no production reader of `state.player.currentTime/duration/preset/lastUpdated` or of any cache-slice field (the production selectors are only `selectCurrentTrack/Volume/IsMuted/IsPlaying/EnhancedStreaming*`). Consequence worth recording on #6039: because `currentTime` is unread, a same-id `player_state` snapshot calling `setCurrentTrack` (which resets `currentTime` to 0 and replaces the `currentTrack` object, `playerSlice.ts:82-93`, `playerStateSnapshot.ts:57`) has no visible effect today, but the object replacement re-renders every `selectCurrentTrack` subscriber (PlaybackSessionProvider at the app root, Player, ComfortableApp, useQueueSubscription) on each snapshot.
- **Evidence**: see the issues above.
- **Impact**: as filed.
- **Suggested Fix**: as filed.

### D2-07: `connection` slice and the error-tracking forward are inert in production
- **Severity**: LOW
- **Dimension**: Redux State Management
- **Location**: `store/middleware/errorTrackingMiddleware.ts:218-231`, `store/middleware/errorCategorization.ts:318-324`, `store/index.ts:41-43`
- **Status**: Existing: #5615 (connection slice write-dead; reader `ConnectionStatusIndicator` orphaned, #5628)
- **Description**: The middleware's only production effect is forwarding `player/setStreamingError` NETWORK errors to `connection.lastError`; nothing in a mounted tree reads `lastError`, and `logToConsole` is `import.meta.env.DEV`, so in production a tracked error is neither logged nor delivered (`onError` is not configured). The `errorCategorization.ts:27` comment cites `useAppErrors` / `useConnectionHealth`, which do not exist. Add to #5615's scope; also `player.streaming.normal` is never written (#5616, open).
- **Evidence**: `store/index.ts:41` passes only `{ logToConsole: import.meta.env.DEV }`.
- **Impact**: Dead error path; no user-visible streaming-error surface depends on it (the UI reads `player.streaming.enhanced.error` directly).
- **Suggested Fix**: As #5615: mount a reader or delete the forward and the middleware's connection coupling.

## Checked and clean
Slice reducer index clamping (`addTrack`/`removeTrack`/`reorderTrack`/`setQueue`/`setCurrentIndex`, #4927/#6038 fixes present); stale-track guards in streaming reducers (#4434, all dispatch sites pass `trackId` except local-failure paths); `startStreaming`/`resetStreaming` ordering on rapid skip; optimistic mutation rollback generations (`queueMutationGuards.ts`, #4836/#5624); serializable state (plain `QueueTrack`/`PlayerTrack`, numbers/strings only; no thunks/classes/Promises stored; default serializable+immutable checks on in the shared test store, no spec disables them); thunk typing and error handling (both thunks are sync, no unhandled promises); `store/index.ts` middleware chain (#3622: logger gated on DEV, no `any` in loggerMiddleware); selector memoization for the live selectors and `useSelector` call sites (no inline object-returning selectors; `useConnectionState` uses `shallowEqual`); sequence watermarks in `playerSyncWatermarks.ts` (#3732/#4338/#4582); `playerSelectors` reuses slice selectors (no duplicate definition); `playerSlice.PresetName` derives from `EnhancementPreset` (adaptive only); loggerMiddleware cost is DEV-only (not reported).
- **Cross-dimension note**: Also found by Dimension 3 as D3-09.

### D9-05: About 2,300 lines of specs pin components no production code mounts
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/library/__tests__/GlobalSearch.test.tsx` (296), `.../library/__tests__/SearchBar.test.tsx` (545), `.../library/__tests__/LibraryHeader.test.tsx` (216), `.../library/__tests__/LibraryEmptyState.test.tsx` (478), `.../library/Search/SearchInput.test.tsx` (45), `.../shared/__tests__/ConnectionStatusIndicator.test.tsx` (382), `hooks/shared/__tests__/useAPIHealthPoll.test.ts` (286), `hooks/shared/__tests__/useAutoHide.test.ts` (93)
- **Status**: Existing: #5628 (open, "33 orphaned component files"); that issue's body already lists every component here, so this is the test-side sibling of that issue
- **Description**: An import-graph walk from `src/index.tsx` confirms these components are unreachable from production. `GlobalSearch`, `useSearchLogic` and `library/Search/*` have no importer outside tests; `library/SearchBar.tsx` is imported only by its own spec. `LibraryHeader`, `LibraryEmptyState`, `ConnectionStatusIndicator` (the hook comment in `useConnectionRedux.ts` calls it "an unmounted component tracked in #5628"), `LibrarySearchControls` and `navigation/SearchBar` are also unreachable. Their specs are green but guard nothing the user can reach. Several recent fixes (#5516 global-search subtitle, #5127, #4449) landed in this dead code. The live top-bar search (`AppTopBarSearchInput`, `useSearchInput`) has its own specs, so the live path is not affected. The `GlobalSearch` spec is also thin: of 12 cases, 9 are placeholders (render, type attribute, focus, long input, unicode, mount/unmount), and none covers result click, stale-request abort, the 2-character minimum, the error path or result grouping in `useSearchLogic`.
- **Evidence**: Reachability script output: `TESTED components/library/Search/GlobalSearch.tsx`, `TESTED components/library/SearchBar.tsx`, `TESTED components/shared/ConnectionStatusIndicator.tsx`, `TESTED components/library/Controls/LibraryHeader.tsx`, `TESTED components/library/LibraryEmptyState.tsx` (unreachable from `index.tsx`, imported only by specs).
- **Impact**: Maintenance and audit time spent on dead code, and a misleading green signal. Whichever way #5628 is resolved, these specs must move with it.
- **Suggested Fix**: Resolve under #5628 (delete each orphan cluster together with its spec, or mount it and strengthen the spec).

## Relationships

- **Second queue consumer (D2-01, D2-02, D2-05, D6-01).** All four touch queue fetch/subscription: the remount re-fetch writes the stale index (D2-01), reconciliation trusts any duplicate-track slot (D2-02), `useQueueSubscription` has an un-reconciled `queue_shuffled.tracks` branch (D2-05), and the retry that should protect the initial fetch never fires (D6-01). Fix D2-01 by making `usePlaylistContextActions` read queue state instead of mounting the hook, then route every queue write through `reconcileQueueIndex`.
- **Contrast cluster (D5-01, D5-02, D8-02).** One root cause: static dark-palette tokens (`tokens.colors.semantic.*`, `accent.primary`) used as text on themed surfaces where `themeVars.*` / `themeVars.accentText` exist. A single sweep plus a source-scan guard, in the style of `spacingTokens.test.ts`, closes all three.
- **Cancellation (D6-02, D6-03, D6-04, D6-10, D6-11).** `useInfiniteAlbums` and playlist fetchers do not forward the React Query signal; `useSearchLogic` and the health poll do not abort on unmount; nine call sites re-check the abort signal on the false premise that the transport mangles aborts.
- **Validation guards (D6-06, D4-06).** Missing `validate` guards on eight GETs and non-null wire types where the backend allows `null` compound each other: unchecked payloads are typed as more certain than the backend promises.
- **Dead code (D1-07, D2-03, D2-04, D5-03, D5-04, D9-05, D4-07).** Orphaned components, unused selectors/primitives/tokens/globals and the specs that pin them. #5628 and #5615 already track the component and connection-slice parts.
- **Focus and keyboard (D8-01, D8-04, D8-05, D1-06).** Two diverging roving-tabindex implementations (D1-06) are the structural reason the track listbox still has stray Tab stops.
- **Test gates (D9-01 with D9-02/03/04).** The weak-test and mock-target gates skip `*.spec.tsx` and `it.each` bodies, and the untested flows (Era sort, settings folder add/remove, EditPlaylistDialog) are exactly where such gaps hide.

## Prioritized Fix Order

1. **D2-01 (+ D2-02, D2-05)**: user-visible wrong-track playback; small fix (stop mounting a second queue hook in the sidebar).
2. **D6-01**: restores the intended retry for initial queue and enhancement-status loads; one-line type-guard change in `retryTransient`.
3. **D6-03, D3-02, D6-02**: request lifecycle races in search, library pagination and album fetch (regression of #5650).
4. **D8-05, D8-04, D8-01**: keyboard and focus defects (Escape closing Settings, extra Tab stops, focus loss on Back).
5. **D5-01 / D5-02 / D8-02**: light-mode contrast sweep with a guard test to stop regrowth.
6. **D7-01, D7-02, D7-03**: virtualize playlist detail; decouple the AlbumCharacterPane animation from React state and honour the visualizations switch.
7. **D8-06**: make single-character shortcuts disable-able or remappable.
8. **LOW cleanup batch**: D6-04/05/06/07/08/09/10/11, D3-04..D3-08, D4-01..D4-07, D1-01..D1-06, D5-03..D5-07, D8-07..D8-10, D9-01..D9-04, D2-03/D2-04.

## Checked and Clean

- Dimension 1: list keys (every `.map` over reorderable data keys on `track.id` / `action.id`; index keys appear only on static skeleton and tab lists; the queue uses occurrence-disambiguated keys), components defined inside components (AST scan found none; the single hit is the `lazyWithRetry` factory), region ErrorBoundary coverage and `resetKeys` for library, player, queue, settings and shortcuts help (one boundary class, `RegionErrorFallback` shared), route lazies via `lazyWithRetry`, `useToast` identity stability (memoised), unmounted-update guards in `useArtworkPalette` and the library fetch hooks (`isActive` / request guard / abort), ref usage for DOM and focus (virtualizer scroll element, focus rAF with cancellation), file-length limit for everything except CozyLibraryView (and AudioPlaybackEngine, now 295).
- Dimension 3: dependency arrays and stale closures in the WebSocket stack (`useWebSocketConnection`, `websocketConnectionCore/State/Lifecycle`, `socketFrameParser` Blob/ArrayBuffer pairing, reconnect queue replay, `useOutgoingChannel`), `useMessageSubscriptions` ref-held subscribe (no hook hand-rolls a subscribe effect except the deliberate refcounted singletons `useScanProgress`/`useArtworkRevision`, closed in #5789), `OutgoingCommand` typed sends (no hand-built `{type, data}` or camelCase `trackId` commands), reconnect-budget single source (`DEFAULT_MAX_RECONNECT_ATTEMPTS`), PlaybackSessionProvider single ownership (no second `usePlayEnhanced`/`AudioContext` outside it; `usePlayEnhanced` called once), `useAutoAdvance` latch and transport gate, stream-start watchdog / seek-retry / fingerprint-status timers (all cleared), `usePlayerStateSync` seq watermarks and server-instance reset, enhancement command guards (`useLatestRequestGuard`, in-flight counter), `useRestAPI` unmount abort and GET-only stale detection, `useLibraryPagination`, `useLibraryScan`, `useLibraryStats`, fingerprint hooks (`useTrackFingerprint`, `useAlbumFingerprint(s)` batching/abort, `useSimilarTracks`), `useFingerprintCoverage`, settings/batch/search-input/progress-bar/keyboard-seek/image-loader/queue-keyboard hooks, `useKeyboardShortcuts` trampoline, single-flight `startPlayback` stop/dispose cancellation (#6043).
- Dimension 4: `any` in production (0), `@ts-ignore/@ts-expect-error/@ts-nocheck` (0), non-null `!` assertions (9, all justified by a preceding check), WS message-type union vs backend `BroadcastMessageType`/`stream_protocol` (all fields agree), binary/text frame discrimination (`audio_chunk_meta` + ArrayBuffer/Blob pairing typed), per-type subscribe handler typing (#5636; only the documented single-site widenings remain), shared unions `RepeatMode`/`StreamType` (single definition, no re-typed literals), `EnhancementPreset` derivation (`'adaptive'` only; no removed preset names, no `as EnhancementPreset` casts), REST types `Track`/`Album`/`Artist`/`LibraryStats`/queue/stats/enhancement-status vs backend serializers, DOM event-handler typing (no untyped handlers), generic constraints in `useWebSocketMessages`/`serviceFactory`/`libraryQueryRequest` (documented boundary casts only), `tsc -p tsconfig.build.json` (0 errors).
- Dimension 5: hardcoded hex/rgb literals (only the documented dev-logger palette #6234, data-driven fingerprint hsla in AlbumCharacterPane, and `fatalInitScreen` which reads tokens); `themeVars` vs `tokens.colors.text|bg` direct reads (none); white-alpha/glass fills (guarded); hex-alpha suffix on `var(--app-*)` (none; the `statusColor` + alpha sites use raw hex); doubled `px` after tokens; spacing literals in `padding/margin/gap` strings (allowlisted); `fontSize` literals (only icon glyph sizes); font weights/families (tokens, fonts bundled via `@fontsource-variable`); line-height literals (documented deliberate); MUI breakpoints derive from `tokens.breakpoints` and `mediaBelow` used for CSS-in-JS; deep `../../` relative imports (guard passes; only `./` sibling imports remain in production); theme applied in `useLayoutEffect`; no stale token references; no Google Fonts; `index.html`/`manifest.json` colours match `bg.level0`.
- Dimension 6: raw-fetch/axios bypass (only `apiRequest.ts` calls `fetch`); one transport (`useRestAPI` is a thin wrapper over `fetchWithTimeout`); camelCase/snake_case mapping (all list/detail GETs go through `api/transformers`); `apiRequest` caller-abort and timeout handling (#5653/#5609: `AbortError` rethrown raw, timeout is status 0); status-aware `shouldRetryQuery` for React Query (no per-call overrides except the two in D6-07); scan timeout (`SCAN_TIMEOUT_MS` passed on both scan call sites, #5643); `getOrNullOn404` usage; `failureMessage` use in settings and playlist flows; response guards on library, album tracks, artist detail, settings, queue, stats, similar tracks, batch fingerprints, create-playlist and add-to-playlist/queue paths; endpoint and method parity with backend routes (`/api/playlists/{id}/tracks/add|reorder`, `/api/player/queue/*`, `/api/library/tracks/{id}/favorite`, `/api/metadata/tracks/{id}`); useRestAPI mutation stale-guard (#5608) and counter-based loading; request cancellation in `useLibraryStats`, `useLibraryQueryFetchers`, fingerprint hooks, `useSimilarTracks`, `useMetadataForm`, album/artist/playlist detail hooks.
- Dimension 7: 10 Hz position tick (PlaybackSession split into Controls/Progress contexts, memoized transport children, `usePlaybackTransport` gated on isPlaying), WebSocket audio_chunk hot path (transferable ArrayBuffer, ring-buffer append, throttled Redux progress dispatch, flow-control hysteresis, bounded pending queue), AudioWorklet feeding (bounded lookahead, ownership transfer), PCMStreamBuffer/AudioPlaybackEngine buffer release on track change (dispose, capacity sized from duration), starfield rAF loop (30 fps cap, idle stop, hidden-tab stop, context-loss handling), audio visualization store (no React state, reused FFT scratch buffer), Redux selectors (no derived-array `useSelector`, field selectors only), WS subscription lifecycle (ref-held handlers, stable keys), scan progress store (`useSyncExternalStore`, per-batch emission), library lists (songs list/grid, albums grid, artist list, queue, artist TracksTab, cache list all virtualized with stable row callbacks and memoized rows), `useLibraryChangeSync` and album-fingerprint batching (per-album query keys, 4-wide concurrency cap, abort wiring), artwork (`size=` thumbnails on every grid, list and player-bar consumer, `loading="lazy"`), polling (health poll pauses when hidden, fingerprint coverage polls only while work is pending, track-fingerprint polling bounded), bundle splitting (lazy library/settings/help, vendor chunk decision documented in `vite.manualChunks.ts`), Toast context value stability, search debounce.
- Dimension 8: keyboard activation of custom buttons (AlbumArt, DropZone, MediaCard, ProgressBar slider, PlaylistList header), ARIA names on icon buttons and settings controls (#5666 holds), dialog roles/names and focus restoration via `useDialogAccessibility` (ClearQueueDialog; MUI dialogs), single `<h1>` per library view and AppViewAnnouncement, now-playing/play-pause/search/loading live regions (polite for status, assertive only for errors), prefers-reduced-motion (one shared hook + global CSS media rule; no second matchMedia), global `:focus-visible` plus per-control focus rings (no control left with `outline:none` and no replacement), landmarks (banner/search/nav/main), `lang`/`<title>`, decorative canvas aria-hidden, no unmounted-component findings reported.
- Dimension 9: weak/zero-assertion specs (`pnpm run test:weak` = 0), `.only`/`.skip`/`.todo`, snapshots (none), floating promises/unawaited `waitFor`/`user.*`, `act(async)` + `rejects` usage, swallowed try/catch in error-path specs (all pair with a discriminating assertion), global WebSocketContext auto-mock (every spec exercising the real context uses `vi.unmock`), MSW unhandled-request opt-out (only `useRestAPI.test.ts`, which stubs `fetch` itself), `vi.mock` target existence guard, integration specs import production modules, baseline file (empty, consistent), player/queue/WebSocket/Redux critical-path coverage (hooks, slices, transport, auto-advance, stale rollback, singleton/reconnect), real-timer sleeps (only negative-assertion waits, bounded), unbounded mock loops (none), type-level specs are run by `type-check` in CI.

Suggested next step: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-11-17.md`
