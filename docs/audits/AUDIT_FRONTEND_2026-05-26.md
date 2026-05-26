# Frontend Audit — 2026-05-26

**Scope**: `auralis-web/frontend/src/` — React 18 + TypeScript + Vite + Redux + MUI
**Depth**: deep (full call-graph tracing)
**Methodology**: 9 dimension agents, each verifying findings against current code; dedup against `gh issue list` and prior `docs/audits/AUDIT_FRONTEND_*.md` reports.

Prior frontend audit (`AUDIT_FRONTEND_2026-03-25.md`) findings status: most fixed; surviving items are either re-reported below with current `FE-NEW-*` IDs or were filed as `#3075`, `#3131`, `#3241`, `#3256`, `#3261`, `#2816`. These remain open and are NOT re-filed here.

---

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 0 |
| HIGH | 10 |
| MEDIUM | 32 |
| LOW | 40 |
| **Total NEW findings** | **82** |

**Plus 2 existing-issue cross-references** (`FE-NEW-155 → #3256`, `FE-NEW-156 → #3131`) included for context; not re-published.

### Themes (where the bugs cluster)

1. **Stacking-context / portal hygiene** — `position: fixed` confirm dialogs trapped inside MUI `backdropFilter` ancestors (`FE-NEW-115`).
2. **Error-boundary coverage gaps** — the entire library subtree has only a `Suspense`, no boundary; a library render error kills the whole app (`FE-NEW-116`).
3. **`useEffect` cleanup discipline** — five hooks fire `fetch()` with no `AbortController` (`FE-NEW-121`, `147`, `154`, `186`, `193`); one event-listener race (`FE-NEW-118`).
4. **`player.currentTrack` duplicates `queue.tracks[currentIndex]`** — three code paths dispatch one without the other, creating a transient (and sometimes permanent) UI desync (`FE-NEW-131`).
5. **WS reconnect drops `shuffle_enabled` and `repeat_mode`** — `usePlayerStateSync` never dispatches those two fields (`FE-NEW-130`).
6. **Type-safety erosion** — 14 `err as ApiError` casts without narrowing (`FE-NEW-163`), 4 handler `as any` casts in `usePlayNormal` (`FE-NEW-160`), `serviceFactory` typed all CRUD IDs as `any` (`FE-NEW-164`), `CacheStatsResponse` shape is stale vs runtime (`FE-NEW-162`).
7. **List-rendering scaling** — TrackGridView, AlbumGrid, ArtistList all render without virtualization (`FE-NEW-201`, `205`, `206`); per-card WS subscriptions in AlbumCard fan out O(n) on every `artwork_updated` (`FE-NEW-200`).
8. **High-frequency player render storms** — `usePlayerStateSync` fires 9 dispatches per `player_state` message at 1 Hz (`FE-NEW-203`); `usePlayerStreaming` polls at 10 Hz and always builds new `bufferedRanges` array (`FE-NEW-204`).
9. **Design-system drift** — light-mode `themeConfig.lightColors` is a parallel hex palette, not derived from tokens (`FE-NEW-176`); `BorderRadius.styles.ts` is a stale shim one scale-step behind (`FE-NEW-178`); 100+ inline transition values bypass `tokens.transitions` (`FE-NEW-181`).
10. **Accessibility gaps in custom controls** — `PlayerEnhancementPanel` mode toggles have no `aria-pressed` (`FE-NEW-216`); design-system `ProgressBar` primitive has no `role="progressbar"` or value attributes (`FE-NEW-218`); settings Sliders unlabelled (`FE-NEW-220`); `TrackRow` uses `role="row"` outside any table context (`FE-NEW-217`); `CacheHealthWidget` interactive Box has no keyboard handler (`FE-NEW-215`).
11. **Tests that don't actually test** — 8 of 22 `usePlaybackControl` tests fail because `currentTrack` is never seeded (`FE-NEW-230`); 47 of 47 `usePlayEnhanced` tests fail because the WS context mock is missing `setResumePositionGetter` (`FE-NEW-231`, regression of #2601); `Player.test.tsx` mocks the entire `react-redux` module, defeating integration coverage (`FE-NEW-234`); `usePlayerStreaming` drift tests never assert `playbackRate` (`FE-NEW-237`) and mask a real direction bug (`FE-NEW-233`).

### Most impactful (single-PR fixes)

1. `FE-NEW-115` — Portal the `ClearQueueDialog` so its `position: fixed` overlay actually covers the screen.
2. `FE-NEW-116` — Wrap `CozyLibraryView` in a dedicated `ErrorBoundary`.
3. `FE-NEW-130` — Two-line fix to dispatch `shuffle_enabled` + `repeat_mode` in `usePlayerStateSync`.
4. `FE-NEW-200` + `FE-NEW-205` — Centralize artwork-revision subscription; virtualize album grids.
5. `FE-NEW-217` — Change `role="row"` to `role="option"` in `TrackRow` (single edit).
6. `FE-NEW-233` — Drift correction always slows down (`Math.abs` strips direction); change to signed comparison.
7. `FE-NEW-231` — Add `setResumePositionGetter: vi.fn()` to the test mock; unlocks 47 dead enhanced-playback tests.

---

## Per-Dimension Index

| Dimension | NEW Findings | HIGH | MEDIUM | LOW |
|-----------|:-:|:-:|:-:|:-:|
| 1. Component Quality | 8 | 1 | 3 | 4 |
| 2. Redux State | 8 | 0 | 2 | 6 |
| 3. Hook Correctness | 11 | 0 | 4 | 7 |
| 4. Type Safety | 10 | 1 | 4 | 5 |
| 5. Design System | 8 | 0 | 4 | 4 |
| 6. API Client | 9 | 0 | 3 | 6 |
| 7. Performance | 8 | 2 | 5 | 1 |
| 8. Accessibility | 11 | 3 | 4 | 4 |
| 9. Test Coverage | 9 | 3 | 3 | 3 |
| **Total** | **82** | **10** | **32** | **40** |

---

## HIGH-severity findings (10)

### FE-NEW-115: ClearQueueDialog position:fixed trapped inside Player's backdropFilter stacking context
- **Dimension**: Component Quality
- **Location**: `components/player/QueuePanel/ClearQueueDialog.tsx:42-57`, `components/player/Player.styles.ts:22`
- **Status**: NEW
- **Description**: `ClearQueueDialog` renders a "fullscreen" confirmation overlay using `position: fixed; inset: 0`. CSS spec requires that an element with `backdrop-filter` creates a new containing block for `position: fixed` descendants. The Player root (`backdropFilter: 'blur(10px) saturate(1.08)'`) and `queuePanelWrapper` both apply `backdropFilter`. The fixed overlay is therefore anchored to the Player container (~400px tall), not the viewport, and is also clipped by `queuePanelWrapper`'s `overflowY: auto; maxHeight: '400px'`.
- **Impact**: Confirmation dialog backdrop appears only inside the queue panel area; cancel/confirm buttons may be partially hidden. Keyboard focus trap still works but visual containment is wrong.
- **Siblings**: `QueueManager.tsx:407-413` has the identical pattern (dead code — see `FE-NEW-117`).
- **Suggested Fix**: Render via `ReactDOM.createPortal(…, document.body)` so the dialog escapes the Player's stacking context.

### FE-NEW-160: `usePlayNormal` suppresses all four WS handler types with `as any`
- **Dimension**: Type Safety
- **Location**: `hooks/enhancement/usePlayNormal.ts:456–471`
- **Status**: NEW
- **Description**: The four handlers (`handleStreamStart`, `handleChunk`, `handleStreamEnd`, `handleStreamError`) have concrete narrowed signatures already assignment-compatible with `MessageHandler` — no cast is needed. The four `as any` casts silence potential genuine type errors and block TS from catching future signature regressions.
- **Impact**: Schema regressions in `audio_stream_start`/`audio_chunk` payloads pass silently.
- **Suggested Fix**: Remove the `as any` casts. Widen each handler to accept `AnyWebSocketMessage | WebSocketMessage` and narrow internally with a type guard, mirroring `usePlaybackQueue.ts`.

### FE-NEW-200: `useArtworkRevision` spawns one WebSocket subscription per rendered AlbumCard — O(n) fan-out
- **Dimension**: Performance
- **Location**: `hooks/library/useArtworkUpdates.ts:24-34`, `components/album/AlbumCard/AlbumCard.tsx:63-64`, `components/album/AlbumArt.tsx:98-99`
- **Status**: NEW
- **Description**: Every mounted `AlbumCard` calls `useArtworkRevision(albumId)`, which calls `useWebSocketSubscription(['artwork_updated'], ...)` internally. With a 200-album grid, 200 callbacks are invoked for every `artwork_updated` broadcast. The album-id filter runs inside each callback after the O(n) dispatch.
- **Impact**: A single `artwork_updated` message triggers up to 500 callback invocations and 500 state comparisons on a fully-loaded library. The `managerReadyListeners` Map also grows O(album-count), re-iterated on every WS reconnect.
- **Suggested Fix**: Replace the per-card hook with a single context- or slice-level `Map<albumId, revision>` updated by one shared subscription. Components read via selector.

### FE-NEW-201: `TrackGridView` renders all loaded tracks without virtualization — grows unbounded
- **Dimension**: Performance
- **Location**: `components/library/Views/TrackGridView.tsx:31-63`
- **Status**: NEW
- **Description**: The grid-mode path calls `tracks.map(...)` with no `useVirtualizer`. The list view path correctly uses `@tanstack/react-virtual` but the grid path was missed. `react-infinite-scroll-component` appends but never removes off-screen nodes. The inline `onPlay` arrow at line 53 also defeats `TrackCard`'s `memo`.
- **Impact**: 1000 tracks = ~1000 `Grid2 + TrackCard` nodes continuously re-rendered on every 1 Hz `player_state` tick.
- **Suggested Fix**: Replace `tracks.map()` with a `useVirtualizer` grid layout. Extract the `onPlay` arrow to a stable `useCallback`.

### FE-NEW-215: CacheHealthWidget interactive `<Box>` missing `role="button"` and keyboard handler
- **Dimension**: Accessibility (WCAG 2.1.1 Level A)
- **Location**: `components/shared/CacheHealthWidget.tsx:169-193`
- **Status**: NEW
- **Description**: When `interactive={true}`, the outer `<Box>` gets `tabIndex={0}` + `onClick` but no `role="button"` and no `onKeyDown`. Keyboard users who Tab to the widget can focus it but cannot activate it with Enter or Space.
- **Suggested Fix**: Add `role="button"` and an `onKeyDown` handler that calls `setShowExpandedMonitor(true)` on Enter/Space.

### FE-NEW-216: `PlayerEnhancementPanel` mode toggle buttons missing `aria-label` and `aria-pressed`
- **Dimension**: Accessibility (WCAG 4.1.2 Level A)
- **Location**: `components/enhancement/PlayerEnhancementPanel.tsx:173-202`
- **Status**: NEW
- **Description**: "Original" and "Enhanced" buttons have only `title` (not reliably exposed by AT). No `aria-pressed` to communicate the active state. Screen readers will announce the emoji characters ("🎵", "✨") instead of the labels.
- **Suggested Fix**: Add `aria-label="Play original audio"` / `aria-label="Play with enhancement"` and `aria-pressed={playMode === 'normal'/'enhanced'}`. Wrap the emoji in `<span aria-hidden="true">`.

### FE-NEW-217: `TrackRow` uses `role="row"` on a `<div>` outside any table/grid context
- **Dimension**: Accessibility (WCAG 1.3.1 Level A)
- **Location**: `components/library/Items/tracks/TrackRow.tsx:100-117`
- **Status**: NEW
- **Description**: `RowContainer` (styled MUI `Box`, renders as `<div>`) sets `role="row"` but is rendered inside `ListViewContainer` which has no `role="table"`, `role="grid"`, or `role="treegrid"` — the `row` role is only valid inside one. `TrackList.tsx:132` uses `role="listbox"` so the correct child role is `role="option"`.
- **Impact**: AT either ignores the role or emits a broken-structure error. NVDA/JAWS/VoiceOver may announce confusing table-navigation cues in a list context.
- **Siblings**: `TrackListViewContent.tsx:167` already uses `role="option"` on its virtual item wrapper — inconsistent.
- **Suggested Fix**: Change `role="row"` to `role="option"`.

### FE-NEW-230: `usePlaybackControl.play()` tests assert unreachable track_id (8 of 22 failing)
- **Dimension**: Test Coverage
- **Location**: `hooks/player/__tests__/usePlaybackControl.test.ts:91-107`
- **Status**: NEW
- **Description**: The test builds a Redux store with `currentTrack: null`, then calls `play()` and asserts `mockSend` was called with `{ track_id: 123 }`. `play()` throws `'No track selected. Set queue first.'` before `send()` runs. The seek/volume tests at lines 240/262 also fail — they index `calls[0][2]` (third argument) but `post()` is a two-argument signature.
- **Impact**: The single most critical user action — pressing play — has no passing test. Regressions in `play()` are completely undetected.
- **Suggested Fix**: Seed the test store with `dispatch(setCurrentTrackAction({ id: 123, ... }))` before each `play()` test. Update seek/volume assertions to match the two-argument `post(url, body)` signature.

### FE-NEW-231: `usePlayEnhanced` test suite fully broken — mock missing `setResumePositionGetter` (47 of 47 failing)
- **Dimension**: Test Coverage
- **Location**: `hooks/enhancement/__tests__/usePlayEnhanced.test.ts:231-248`
- **Status**: Regression of #2601
- **Description**: Issue #2601 was filed for missing enhanced-playback tests. A 1059-line, 47-test file was written but **all 47 fail**. The per-test mock supplied to `vi.mocked(useWebSocketContext)` omits `setResumePositionGetter` (added in #3373). The hook calls it on mount → `TypeError`. Cascading `Should not already be working.` errors kill the remaining 46 tests via React Scheduler.
- **Impact**: Enhanced playback (PCM streaming, chunk accumulation, auto-start, seekTo) has zero effective coverage.
- **Suggested Fix**: Add `setResumePositionGetter: vi.fn()` to the per-test mock. Extract a `makeMockWsContext()` factory shared with `src/test/setup.ts` to prevent future drift.

### FE-NEW-232: `usePlayerStateSync` implementation diverges from test expectations (19 failing)
- **Dimension**: Test Coverage
- **Location**: `hooks/player/usePlayerStateSync.ts:68` / `__tests__/usePlayerStateSync.test.ts`
- **Status**: NEW
- **Description**: Tests expect selective dispatch (only when the field is present in the message). The implementation dispatches `setIsPlaying(state.is_playing)`, `setCurrentTime(state.current_time)`, etc. unconditionally — so `{ queue: [...] }` with no `is_playing` key dispatches `setIsPlaying(undefined)`, overwriting valid state. Also: `current_track` mapping uses `artwork_url` but the fixture uses `album_art` — field-name divergence between fixtures and `TrackInfo` type.
- **Impact**: Every partial WS update silently overwrites `isPlaying`, `currentTime`, `duration`, `isMuted` with `undefined`/`NaN`, causing UI breakage.
- **Suggested Fix**: Guard each dispatch with `if ('is_playing' in state)`. Align `TrackInfo` field names; add fallback mapping for `artwork_url` vs `album_art`.

---

## MEDIUM-severity findings (32)

### Dimension 1 — Component Quality

#### FE-NEW-116: Library/enhancement subtrees have no dedicated ErrorBoundary
- **Location**: `ComfortableApp.tsx:326-336`, `components/library/CozyLibraryView.tsx`, `components/library/AlbumCharacterPane/AlbumCharacterPane.tsx`
- **Status**: NEW
- **Description**: `Player` is wrapped (fixed in #3115) but `CozyLibraryView` is only inside `<Suspense fallback={null}>`. A render-time throw in any library component propagates to the root `ErrorBoundary`, killing the entire UI rather than isolating to the library pane.
- **Suggested Fix**: Wrap `CozyLibraryView` in `<ErrorBoundary fallback={<LibraryErrorFallback />}>` in `ComfortableApp.tsx`. Add inner boundary at `AlbumCharacterPane` to isolate fingerprint-visualization crashes.

#### FE-NEW-117: `QueueManager` component is dead code (495 lines, broken position:fixed modal pattern)
- **Location**: `components/shared/QueueManager.tsx:1-495`
- **Status**: NEW
- **Description**: Zero live imports. Contains the same `position: fixed + zIndex.dropdown` modal pattern as `FE-NEW-115`, plus an inaccessible HTML5 drag-and-drop queue.
- **Suggested Fix**: Delete the file.

#### FE-NEW-118: ConnectionStatusIndicator health-poll interval race on visibility change
- **Location**: `components/shared/ConnectionStatusIndicator.tsx:105-154`
- **Status**: NEW
- **Description**: Cleanup runs `stopPolling()` (sets `interval = null`) then `removeEventListener('visibilitychange', ...)`. A visibility event firing between the two calls can call `startPolling()` and create a new interval that is never cleaned up.
- **Suggested Fix**: Use an `intervalRef` so cleanup can always clear the latest interval regardless of closure state. Reverse the cleanup order: `removeEventListener` first, then `clearInterval`.

### Dimension 2 — Redux State

#### FE-NEW-130: `usePlayerStateSync` silently drops `shuffle_enabled` and `repeat_mode` on reconnect
- **Location**: `hooks/player/usePlayerStateSync.ts:55-127`
- **Status**: NEW
- **Description**: `RawPlayerStateData` carries `shuffle_enabled` and `repeat_mode`, but the hook never dispatches `setIsShuffled` or `setRepeatMode`. After a WS reconnect, Redux state diverges from backend until manual toggle.
- **Suggested Fix**: Add `dispatch(reduxSetIsShuffled(state.shuffle_enabled))` and `dispatch(reduxSetRepeatMode(state.repeat_mode))` to the `player_state` handler alongside the existing queue syncs.

#### FE-NEW-131: `player.currentTrack` duplicates `queue.tracks[currentIndex]` — desync window on local track change
- **Location**: `store/slices/playerSlice.ts:39`, `hooks/enhancement/usePlayNormal.ts:510`, `hooks/enhancement/usePlayEnhanced.ts:622`, `components/player/Player.tsx:103,127`
- **Status**: NEW
- **Description**: Three code paths dispatch `setCurrentTrack` without `setCurrentIndex`. `usePlayNormal.ts:510` never updates the queue at all. 10 consumers read `selectCurrentTrack`; queue consumers read `selectCurrentQueueTrack`. They can diverge transiently (between dispatches) or permanently (if the WS confirmation never arrives).
- **Suggested Fix**: Remove `currentTrack` from `playerSlice`; derive via `selectCurrentQueueTrack`. Short-term: pair every `setCurrentTrack` with `setCurrentIndex`.

### Dimension 3 — Hook Correctness

#### FE-NEW-145: `usePlayNormal` subscription effect includes unstable handlers in deps
- **Location**: `hooks/enhancement/usePlayNormal.ts:455-479`
- **Status**: NEW
- **Description**: Subscription effect lists `handleStreamStart`/`handleChunk`/`handleStreamEnd`/`handleStreamError` in deps. `usePlayEnhanced` (sibling hook) correctly uses ref indirection at `:767-810`. Any future non-stable dep added to a handler tears down all four subscriptions on every render, dropping audio chunks in the gap.
- **Suggested Fix**: Mirror `usePlayEnhanced` — store each handler in a ref outside the effect; subscribe via wrapper closures.

#### FE-NEW-146: `useBatchOperations` returns three new function references on every render
- **Location**: `hooks/shared/useStandardizedAPI.ts:413-468`
- **Status**: NEW
- **Description**: `executeBatch`, `favoriteTracks`, `removeTracks` are inline async functions inside the return object — no `useCallback`. Compare to the well-memoized `useRestAPI.ts:339-347` pattern.
- **Suggested Fix**: Wrap all three in `useCallback([])`; wrap the return object in `useMemo`.

#### FE-NEW-147: `useArtworkPalette` has no abort/cleanup on unmount
- **Location**: `hooks/app/useArtworkPalette.ts:73-122`
- **Status**: NEW
- **Description**: `extractColors` awaits `extractArtworkColors` then calls `setLoading`/`setPalette` on a possibly-unmounted component. The `currentAlbumIdRef.current === albumId` guard protects against album-change but not unmount. `useLibraryStats.ts` handles this correctly via `AbortController`.
- **Suggested Fix**: Add an `isActive` flag (or `AbortController`) cleared in the effect cleanup; gate all `setState` calls on it.

#### FE-NEW-157: `usePlayerStreaming` Layer 2 WS subscription — `onDriftDetected` inline-callback dep causes resubscribe per parent render
- **Location**: `hooks/player/usePlayerStreaming.ts:260-331`
- **Status**: NEW
- **Description**: `onDriftDetected` (caller-provided callback, typically an inline arrow) is in the dep array — subscription tears down and rebuilds on every parent render. During the gap, `position_changed` events can be missed, leaving drift uncorrected for up to 5 s.
- **Suggested Fix**: Store `onDriftDetected` in a ref updated each render; remove from effect deps. Same applies to Layer 3 at line 390.

### Dimension 4 — Type Safety

#### FE-NEW-161: `usePlaylistWebSocket` subscribes to typed WS events with `message: any`
- **Location**: `components/playlist/usePlaylistWebSocket.ts:6, 38, 56`
- **Status**: NEW
- **Description**: Bypasses well-typed `PlaylistUpdatedMessage` / `PlaylistDeletedMessage`. Backend renames (e.g., `playlist_id` → `id`) are invisible to TS.
- **Suggested Fix**: Replace `message: any` with the concrete types.

#### FE-NEW-162: `CacheStatsResponse` in `types/api.ts` declares `overall.hit_rate` but runtime uses `overall.overall_hit_rate`
- **Location**: `types/api.ts:333-354`
- **Status**: NEW
- **Description**: All real consumers read `overall.overall_hit_rate`. The canonical type is `services/api/standardizedAPIClient.ts:CacheStats`. The `types/api.ts` variant is stale.
- **Suggested Fix**: Delete `CacheStatsResponse` from `types/api.ts` and re-export `CacheStats` under that name, or update the interface.

#### FE-NEW-163: `err as ApiError` pattern used without narrowing — 14 call sites
- **Location**: 5 hooks, 14 call sites (see dim 4 report for exact list)
- **Status**: NEW
- **Description**: `err instanceof Error ? ... : (err as ApiError)` assumes any non-Error throw is an `ApiError`. WebSocket disconnects, network timeouts, `DOMException` can throw plain values. `ApiErrorHandler.parse(err)` already exists and handles unknowns.
- **Suggested Fix**: Replace each cast with `ApiErrorHandler.parse(err)`.

#### FE-NEW-164: `serviceFactory.ts` uses `any` for all CRUD IDs and params — infects derived services
- **Location**: `utils/serviceFactory.ts:27-32, 41, ...`
- **Status**: NEW
- **Description**: `CrudEndpoints` types `get`/`update`/`delete` all as `(id: any)`. Affects `playlistService`, `queueService`, `settingsService`, `artworkService`.
- **Suggested Fix**: Add generic `ID = number` parameter to `createCrudService<T, U, ID>`. Replace `(id: any)` with `(id: ID)`.

### Dimension 5 — Design System

#### FE-NEW-175: `exportInfrastructure.ts` uses a complete parallel color palette outside tokens
- **Location**: `utils/exportInfrastructure.ts:171-187`
- **Status**: NEW (continuation of prior DIM-5-DS-04)
- **Description**: 14+ raw hex values including forbidden `#0A0A0A` pure black. Off-brand colors: `#4FC3F7` (Material cyan ≠ `tokens.colors.accent.secondary` `#47D6FF`), `#FFB74D`, `#FF6B6B`, etc.
- **Siblings**: `AnalysisExportService.ts:704,728,751,761,775,799,800`.
- **Suggested Fix**: Add `tokens.export.darkPalette`/`lightPalette` blocks; import from there.

#### FE-NEW-176: `lightColors` in `themeConfig.ts` is a standalone palette bypassing tokens
- **Location**: `theme/themeConfig.ts:57-87`
- **Status**: NEW
- **Description**: 12 raw hex values for light theme. Semantic colors diverge: `success #00a388` vs token `#10B981`, `error #e63946` vs token `#EF4444`. Live in production for theme-switching users.
- **Suggested Fix**: Add `lightMode` sub-object to `tokens.ts`; replace `lightColors` raw hex with token references.

#### FE-NEW-177: AlbumCharacterPane visualization components invent off-palette brand colors
- **Location**: `components/library/AlbumCharacterPane/GlowingArc.tsx:40-66`, `CharacterTags.tsx`, `PanePlaceholders.tsx:149`, `BatchActionsToolbarStyles.ts:17`
- **Status**: NEW
- **Description**: `rgba(0,200,220)` (off-spec teal), `rgba(180,130,255)` (off-palette violet), `rgba(118,75,162,0.95)` (off-brand purple in toolbar). None defined in tokens.
- **Suggested Fix**: Add `tokens.colors.audioSemantic.spatialAlt/harmonicLight/harmonicGlow` for visualization variants, or use `withOpacity()` on existing tokens.

#### FE-NEW-178: `BorderRadius.styles.ts` is a stale shim one scale-step behind tokens
- **Location**: `components/library/Styles/BorderRadius.styles.ts:23-67`
- **Status**: NEW
- **Description**: Plain string constants: `radiusMedium='8px'` vs current `tokens.borderRadius.md='12px'`. Imported by `Skeleton.styles.ts`, `Button.styles.ts`, `Avatar.styles.ts`. Skeletons render 4px tighter corners than the real content they're placeholding.
- **Suggested Fix**: Replace constants with `tokens.borderRadius.*` references.

### Dimension 6 — API Client

#### FE-NEW-185: `retryWithBackoff` retries 404/400 in processingService
- **Location**: `services/processingService.ts:244-248`, `utils/errorHandling.ts:79-115`
- **Status**: NEW
- **Description**: `getJobStatus()` / `downloadResult()` call `retryWithBackoff` without a `shouldRetry` predicate. The implementation's guard requires the predicate to be defined; without it, every error including HTTP 404 / 400 is retried 3 times.
- **Suggested Fix**: Pass `shouldRetry: isRetryableError` (already exported from `errorHandling.ts`).

#### FE-NEW-186: `useAlbumDetails` and `useArtistDetailsData` have no AbortController
- **Location**: `components/library/Details/useAlbumDetails.ts:33-83`, `useArtistDetailsData.ts:30-66`, `useMetadataForm.ts:40-48`
- **Status**: NEW
- **Description**: Three hooks fire `fetch()` in `useEffect` with no `AbortController`. setState on unmounted component if navigation happens mid-fetch.
- **Suggested Fix**: Create `AbortController` per effect, pass `signal` to fetch, abort in cleanup; suppress `AbortError` in catch.

#### FE-NEW-187: `useLibraryData.loadMore` advances offset before confirming response
- **Location**: `hooks/library/useLibraryData.ts:154-167`
- **Status**: NEW
- **Description**: `offsetRef.current = newOffset` runs at line 146 (before fetch); non-OK responses fall through silently, leaving offset permanently advanced. Subsequent calls skip 50 tracks. The canonical `useLibraryWithStats` advances after success.
- **Suggested Fix**: Move offset advance inside `if (response.ok)`; surface error in else branch.

### Dimension 7 — Performance

#### FE-NEW-202: Inline `onClick` arrow defeats `AlbumCard` memo
- **Location**: `components/library/Items/albums/AlbumGridContent.tsx:57`, `AlbumGrid.tsx:78`
- **Status**: NEW
- **Description**: `AlbumCard` is wrapped in `memo` but receives a new inline `onClick` arrow every parent render. In a 200-album grid, every state change triggers 200 `AlbumCard` re-renders.
- **Suggested Fix**: Stabilize via `useCallback`; or restructure `AlbumCard` to take `(albumId, onAlbumClick)` and bind internally.

#### FE-NEW-203: `usePlayerStateSync` 9 sequential Redux dispatches per WS message
- **Location**: `hooks/player/usePlayerStateSync.ts:64-119`
- **Status**: NEW
- **Description**: At 1 Hz during playback, 9 dispatches in a single WS callback. React 18 automatic batching may not extend to WS callbacks (outside React's scheduler).
- **Suggested Fix**: Wrap in `batch()` from `react-redux`, or consolidate into a single `setPlayerState(snapshot)` action.

#### FE-NEW-204: `usePlayerStreaming` 100ms loop builds new `bufferedRanges` array every tick
- **Location**: `hooks/player/usePlayerStreaming.ts:220-257`
- **Status**: NEW
- **Description**: 10 Hz interval. `getBufferedRanges` returns a new array every call. The `setState` guard compares `bufferedPercentage` (changes slowly) but always spreads `bufferedRanges` into new state → 10 React re-renders/sec of the player subtree.
- **Suggested Fix**: Compare array length + range values before updating; skip state update if nothing changed. Round `currentTime` to render-visible precision (0.1 s).

#### FE-NEW-205: Album grids grow unbounded without virtualization
- **Location**: `components/library/Items/albums/AlbumGridContent.tsx:46-74`, `AlbumGrid.tsx:66-107`, `CozyAlbumGrid.tsx:149`, `EraSection.tsx:88`
- **Status**: NEW
- **Description**: All accumulated albums rendered with `.map()`. Each carries a `useArtworkRevision` subscription. 500 albums = 500 live nodes.
- **Suggested Fix**: `@tanstack/react-virtual` grid mode (already a project dep). Compound fix with `FE-NEW-200`.

#### FE-NEW-206: Artist list no virtualization + missing `memo` on `ArtistSection`
- **Location**: `components/library/Items/artists/ArtistListContent.tsx:104-112`, `ArtistSection.tsx:33-39`
- **Status**: NEW
- **Description**: `ArtistSection` not wrapped in `memo`; receives inline `onContextMenu` arrow. Every context-menu open/close re-renders all 26 letter groups and all artists inside them.
- **Suggested Fix**: Wrap `ArtistSection` in `memo`; stabilize the `onContextMenu` handler at the parent.

### Dimension 8 — Accessibility

#### FE-NEW-218: Design-system `ProgressBar` primitive missing `role="progressbar"` and all ARIA value attributes
- **Location**: `design-system/primitives/ProgressBar.tsx:76-89`
- **Status**: NEW
- **Description**: Two plain `<div>`s with no ARIA semantics. The `label` prop is visually shown but not programmatically associated. As the design-system primitive, all consumers inherit the deficiency.
- **Suggested Fix**: Add `role="progressbar"`, `aria-valuenow={Math.round(percentage)}`, `aria-valuemin={0}`, `aria-valuemax={100}` to the inner bar. Associate the label via stable `id` + `aria-labelledby`.

#### FE-NEW-219: `SegmentedControl` toggle group has no accessible name
- **Location**: `design-system/primitives/SegmentedControl.tsx:136-153`
- **Status**: NEW
- **Description**: No `role="group"` and no `aria-label`. Screen readers announce each button in isolation without indicating mutual exclusion. The prop interface offers no `aria-label` field.
- **Suggested Fix**: Add `aria-label?: string` to props; apply `role="group"` and `aria-label={...}` on the container. Pass `aria-label="Sort albums by"` at `LibraryViewRouter.tsx:138-143`.

#### FE-NEW-220: Settings Sliders in `PlaybackSettingsPanel` and `EnhancementSettingsPanel` have no accessible label
- **Location**: `components/settings/PlaybackSettingsPanel.tsx`, `EnhancementSettingsPanel.tsx:71-79`
- **Status**: NEW
- **Description**: Three `<Slider>` instances preceded by `<SectionLabel>` (`<p>`-equivalent, not `<label>`). No `aria-label` / `aria-labelledby` / `getAriaLabel`. MUI's `Slider` renders `<input type="range">` internally; without a label, AT announces only the value.
- **Suggested Fix**: Add `aria-label` to each `<Slider>`.

#### FE-NEW-221: `TrackRow` MoreButton icon-only button missing `aria-label`
- **Location**: `components/library/Items/tracks/TrackRow.tsx:152-159`
- **Status**: NEW
- **Description**: Equivalent button in `TrackTableRowItem.tsx:94-97` already has `aria-label={`More options for ${track.title}`}`. The library Songs view (`TrackRow`) was missed.
- **Suggested Fix**: Add the same `aria-label`.

### Dimension 9 — Test Coverage

#### FE-NEW-233: Drift direction always 0.95 — `usePlayerStreaming` applies wrong rate correction
- **Location**: `hooks/player/usePlayerStreaming.ts:281` / `__tests__/usePlayerStreaming.test.ts:314-338`
- **Status**: NEW
- **Description**: `drift = Math.abs(localPosition - serverPosition)` (always ≥ 0); `playbackRate = drift > 0 ? 0.95 : 1.05` is **always 0.95**. When server is ahead (local needs to catch up), player slows down further. Test asserts only `serverCurrentTime`, never `playbackRate`.
- **Suggested Fix**: Replace `drift > 0` with `localPosition > serverPosition` (signed). Add assertion `expect(mockAudioElement.playbackRate).toBe(1.05)` when local is behind.

#### FE-NEW-234: `Player.test.tsx` mocks `react-redux` entirely — Redux integration tests defeated
- **Location**: `components/player/__tests__/Player.test.tsx:26-51`
- **Status**: NEW
- **Description**: Hand-rolled mock: `useSelector` uses a name-keyed lookup table returning `undefined` for unknown selectors; `useDispatch` is no-op. All 5 tests are structural ("does it render/import?"). No state-driven behavior tested. `TrackInfo.test.tsx:12` has the same pattern.
- **Suggested Fix**: Replace the module mock with a real Provider wrapping a pre-populated test store (pattern from `usePlaybackControl.test.ts`).

#### FE-NEW-235: `fireEvent.change` used for controlled inputs — bypasses React synthetic events
- **Location**: `LibraryComponents.test.tsx:392,471,500`, `PlayerControls.test.tsx:234`
- **Status**: NEW
- **Description**: `fireEvent.change` skips browser-level event processing (focus, beforeinput, keydown/up, composition) that React 18 relies on. `userEvent.setup()` is imported in the same files but applied inconsistently.
- **Suggested Fix**: Replace with `await userEvent.type(...)` / `await userEvent.clear(...)`. For sliders, use `fireEvent.input` or `userEvent.pointer`.

---

## LOW-severity findings (40)

### Dimension 1 — Component Quality (4)
- **FE-NEW-119** — `QueueStatisticsPanel.tsx:142,158,174`: TopItemRow keys combine value + index (Existing: #3075, still open).
- **FE-NEW-120** — `WaveformVisualization.tsx:63`: array index as React key for frequency-band bars. Functionally safe (bands don't reorder); lint warning.
- **FE-NEW-121** — `useSimilarTracks.ts:111-220`: `fetch` has no `AbortController`. Stale-state risk is mitigated by `currentRequestRef`; resource leak only. (See also `FE-NEW-193`.)
- **FE-NEW-122** — `CozyLibraryView.tsx:280-284`: inline `onTrackPlay` arrow to `SimilarTracksModal`. Minor — no correctness issue; defeats memo if modal is ever memoized.

### Dimension 2 — Redux State (6)
- **FE-NEW-132** — `usePlayerStateSync` fires 10 individual dispatches per message (cf. `FE-NEW-203`).
- **FE-NEW-133** — `useQueue`/`useCache`/`useConnection` return new objects every render. `usePlayer` was memoized in #2537; siblings missed.
- **FE-NEW-134** — `selectQueueState` duplicates `remainingTime`/`totalTime` reductions instead of composing `selectRemainingTime`/`selectTotalQueueTime`.
- **FE-NEW-135** — `createMemoizedSelector` keeps one shared cache slot; two callers with different args thrash silently.
- **FE-NEW-136** — `loggerMiddleware` included in production bundle; `errorTrackingMiddleware` has `logToConsole: true` unconditionally.
- **FE-NEW-137** — `CacheStats.tracks` `Record` stored verbatim in Redux; grows unboundedly with large libraries.

### Dimension 3 — Hook Correctness (7)
- **FE-NEW-148** — `usePlayEnhanced/usePlayNormal`: `[isPlaying, isPaused]` dual-dep causes redundant `pausePlayback()` calls per transition.
- **FE-NEW-149** — `useMasteringRecommendation` cache-hit path never calls `setIsLoading(false)`; stuck-loading after rapid track change.
- **FE-NEW-150** — `usePlayerStreaming` deps list `driftThreshold` (ms) but closure uses derived `driftThresholdSeconds`. Currently safe; refactor-fragile.
- **FE-NEW-151** — `useInitializeAPI`: three config fields (`retryAttempts`, `cacheResponses`, `cacheTTL`) silently stale; missing from dep array.
- **FE-NEW-152** — `usePlaybackQueue`: `toggleShuffle` / `setRepeatMode` use `dispatch` but omit it from `useCallback` deps (inconsistent with siblings).
- **FE-NEW-153** — `useWebSocketSubscription`: module-level `_managerVersionListeners` / `managerReadyListeners` accumulate across Vite HMR reloads (no `import.meta.hot.dispose`).
- **FE-NEW-154** — `usePlayerAPI.fetchPlayerStatus` has no `AbortController`. (See also `FE-NEW-193`.)

### Dimension 4 — Type Safety (5)
- **FE-NEW-165** — `useLibraryQuery.extractItemsFromResponse(response: any)`; switch has no `never` exhaustiveness check.
- **FE-NEW-166** — `useAlbumDetails`: uses `DetailTrack` in reduce but `(t: any)` in adjacent map.
- **FE-NEW-167** — `useSearchLogic`: three untyped `get()` calls; `.map((track: any) => ...)`. `LibraryViewRouter.onTrackPlay?: (track: any)` propagates.
- **FE-NEW-168** — `TrackInfo.filepath: string` (required) in frontend but `Field(exclude=True)` in backend `player_state.py:TrackInfo`. `queue_recommender.ts:114` receives `undefined`.
- **FE-NEW-169** — `buildQueryParams(params: Record<string, any>)` allows objects as values; `String()` silently produces `[object Object]`.

### Dimension 5 — Design System (4)
- **FE-NEW-179** — `index.css`: `rgba(226,232,240,...)` (slate-200, `--silver`) used 5× as border; not in tokens.
- **FE-NEW-180** — Design-system primitives (`SegmentedControl`, `Input`, `Modal`) use raw `rgba()` including pure-black modal backdrop (Style Guide §1 violation).
- **FE-NEW-181** — `tokens.transitions.*` bypassed in 100 locations across 60 files (dominant pattern: `'all 0.2s'` / `'all 0.3s ease'`).
- **FE-NEW-182** — Off-token font sizes: `10px` (below `xs=11px` floor, WCAG concern), `17px`, `48px`, `60px`, `80px` across 7 files; `IconButton` uses raw `18/20/24px`.
- **FE-NEW-183** — `AuroraWaveIcon.tsx`: `stroke="white"` on all 3 paths; invisible on light theme.

### Dimension 6 — API Client (6)
- **FE-NEW-188** — `usePlaybackState`: builds URL with raw `import.meta.env.VITE_API_URL` instead of `getApiUrl()`.
- **FE-NEW-189** — `ComfortableApp`: 4 raw fire-and-forget `fetch()` for player controls; no `response.ok` check; `PLAYER_PLAY`/`PLAYER_PAUSE` endpoints were removed from backend.
- **FE-NEW-190** — `useMetadataForm.fetchMetadata` trusts raw `response.json()` shape; `|| {}` fallback masks contract breakage.
- **FE-NEW-191** — `useAlbumFingerprints` batch fires `Promise.allSettled` with no concurrency limit; 200 albums = 200 simultaneous GETs.
- **FE-NEW-192** — `useLibraryData` / `useLibraryWithStats` are dual live implementations; bug fixes don't flow between them (cf. `FE-NEW-187`).
- **FE-NEW-193** — `useSimilarTracks.findSimilar` `fetch` has no `AbortController`.

### Dimension 7 — Performance (1)
- **FE-NEW-207** — `useAudioVisualization` rAF loop restarts on `isAudioActive` change; dropped frame on play/pause transition.

### Dimension 8 — Accessibility (4)
- **FE-NEW-222** — Queue toggle button missing `aria-controls` link to the panel region.
- **FE-NEW-223** — `QueuePanel` uses `role="listbox"` + `aria-selected` for the playback queue; `role="list"` + `aria-current="true"` is semantically correct.
- **FE-NEW-224** — `TrackInfo` empty-state musical-note icon (`♪`) missing `aria-hidden="true"` (other artwork placeholder icon at line 46 is already hidden).
- **FE-NEW-225** — `ProgressBar.styles.ts:srOnly` uses deprecated `clip: rect(0,0,0,0)`; live region uses `assertive` for non-urgent seek updates.

### Dimension 9 — Test Coverage (3)
- **FE-NEW-236** — `error-handling.test.tsx`: 4 inline test components use floating `.then().then()` chains inside `useEffect`, no `.catch()`; errors silently swallowed.
- **FE-NEW-237** — `usePlayerStreaming` drift test never asserts intermediate `playbackRate` mutation; "restore to 1.0" test passes vacuously.
- **FE-NEW-238** — `usePlaybackQueue.test.ts` mocks both `useRestAPI` and `useWebSocketSubscription`; real-time queue-update path is never exercised.

---

## Cross-dimension Relationships

1. **Stale-WS-state cluster** (`FE-NEW-130`, `FE-NEW-131`, `FE-NEW-203`, `FE-NEW-232`): four findings around `usePlayerStateSync`. The right fix is to consolidate into a single `setPlayerState(snapshot)` action with selective dispatch, then add the missing shuffle/repeat fields. One PR can close all four.

2. **`useArtworkRevision` x AlbumGrid scaling** (`FE-NEW-200` + `FE-NEW-205`): two HIGH-impact findings that compound. Fixing `FE-NEW-200` (centralize subscription) is a prerequisite for safe AlbumGrid virtualization (`FE-NEW-205`); otherwise virtualization just removes DOM nodes while keeping subscriptions in unmounted hook instances.

3. **No-AbortController cluster** (`FE-NEW-121`, `FE-NEW-147`, `FE-NEW-154`, `FE-NEW-186`, `FE-NEW-193`): five hooks share the same omission. A repo-wide pattern audit + helper utility (`useAbortableFetch`) would close all five.

4. **Drift-correction triangle** (`FE-NEW-233` + `FE-NEW-237` + `FE-NEW-157`): the logic bug (`FE-NEW-233`, always slow down) is masked by the missing test assertion (`FE-NEW-237`). The hook also re-subscribes per parent render (`FE-NEW-157`), missing `position_changed` events in the gap. All three should be fixed in one PR for `hooks/player/usePlayerStreaming.ts`.

5. **Library-view ErrorBoundary x dual-hook divergence** (`FE-NEW-116` + `FE-NEW-187` + `FE-NEW-192`): The library view has no error boundary, AND it uses the divergent `useLibraryData` (with the broken `loadMore`). The boundary plus the migration to `useLibraryWithStats` should be a coordinated cleanup of `CozyLibraryView`.

6. **Test-mocks-defeat-tests cluster** (`FE-NEW-230`, `FE-NEW-231`, `FE-NEW-232`, `FE-NEW-234`, `FE-NEW-238`): five findings. Net result is that a sizable chunk of the player/queue test suite is either silently failing or vacuously passing. The shared fix is a single `makeMockWsContext()` factory + an example real-Provider integration template.

7. **Token-bypass cluster** (`FE-NEW-175`, `FE-NEW-176`, `FE-NEW-177`, `FE-NEW-180`): four findings across exports, light theme, visualization, and primitives. None are critical individually but together they form a slow-drift toward brand fragmentation.

---

## Prioritized Fix Order

### Tier 1 — Ship-quality regressions (1 PR each, surgical)

1. **`FE-NEW-217`** — `role="row"` → `role="option"` in `TrackRow`. One-character fix; immediate WCAG win.
2. **`FE-NEW-130`** — Add `setIsShuffled` + `setRepeatMode` dispatches in `usePlayerStateSync`. Two-line fix.
3. **`FE-NEW-233`** — Replace `drift > 0 ?` with signed comparison in `usePlayerStreaming`. Plus update test assertion.
4. **`FE-NEW-231`** — Add `setResumePositionGetter: vi.fn()` to `usePlayEnhanced` test mock. Unlocks 47 dead tests.
5. **`FE-NEW-115`** — Portal `ClearQueueDialog` via `ReactDOM.createPortal`.
6. **`FE-NEW-117`** — Delete `QueueManager.tsx` (495 dead lines).
7. **`FE-NEW-183`** — `stroke="white"` → `stroke="currentColor"` in `AuroraWaveIcon`. One-character fix per path.

### Tier 2 — Single-PR cleanups (medium effort)

8. **`FE-NEW-116`** — `ErrorBoundary` around `CozyLibraryView` (+ `AlbumCharacterPane`).
9. **`FE-NEW-200`** — Centralize artwork-revision subscription into a single shared listener.
10. **`FE-NEW-230` + `FE-NEW-232`** — Seed `currentTrack` in `usePlaybackControl` tests; guard dispatches in `usePlayerStateSync`.
11. **`FE-NEW-160`** — Remove four `as any` casts in `usePlayNormal`; add type guards.
12. **`FE-NEW-218`** — Add `role="progressbar"` + value attrs to design-system `ProgressBar`.
13. **`FE-NEW-216`** — Add `aria-pressed` + `aria-label` to `PlayerEnhancementPanel` toggles.
14. **`FE-NEW-215`** — Add `role="button"` + `onKeyDown` to `CacheHealthWidget`.
15. **`FE-NEW-220`** + **`FE-NEW-221`** — Slider labels + MoreButton label.

### Tier 3 — Larger restructures (multi-PR)

16. **`FE-NEW-201` + `FE-NEW-205` + `FE-NEW-206`** — Virtualization migration for TrackGridView + AlbumGrid + ArtistList.
17. **`FE-NEW-131`** — Decide on `player.currentTrack` vs `queue.tracks[currentIndex]`; remove duplication.
18. **`FE-NEW-176` + `FE-NEW-178`** — Token alignment for light theme + BorderRadius shim.
19. **`FE-NEW-192`** — Complete migration from `useLibraryData` to `useLibraryWithStats`; delete deprecated.
20. **`FE-NEW-234` + `FE-NEW-238`** — Replace whole-module mocks with real Provider/test store; add `queue_changed` WS integration tests.

### Tier 4 — Defer / track

- LOW-severity items: schedule as opportunistic cleanup during related work.
- `FE-NEW-181` (transitions): codemand-friendly; defer to a single mass-edit PR after auto-mode authorization.
- `FE-NEW-153` (HMR cleanup): development-only; low priority.

---

*Audit performed by 9 parallel dimension agents (Claude Sonnet 4.6) coordinated by /audit-frontend on 2026-05-26.*
*Full per-dimension reports archived at `/tmp/audit/frontend/dim_{1..9}.md` (transient; cleaned up post-merge).*
