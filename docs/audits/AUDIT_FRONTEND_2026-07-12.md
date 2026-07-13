# Frontend Audit — 2026-07-12

**Scope**: Auralis React frontend (`auralis-web/frontend/src/`) — components, Redux store, hooks, TypeScript types, design system, API clients, performance, accessibility, tests. Backend/engine/Rust out of scope.

**Method**: 9 dimension agents (deep depth), fresh read of current source. Deduplicated against 183 frontend-labeled GitHub issues (26 open / 157 closed) and cross-dimension overlaps.

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 22 |
| LOW | 39 |
| **Total** | **62** |

**Key themes**

1. **Sibling-fix drift is the dominant pattern.** The codebase has been hardened by many prior audits; the majority of NEW findings are the *one sibling that got missed* when a fix was applied elsewhere: `usePlayTrack` never got the abort-before-replace that `usePlayEnhanced`/`usePlayNormal` have (H3-01); `usePlaybackControl` never got the `useMemo` return that three sibling hooks have (M3-02); `queueService.getQueue()` never got the array/object shape fix applied to `settingsService` (A6-01); `useQueueRecommendations` never got the warn-once guard its two siblings received (L3-01); several IconButtons never got the `aria-label` that `SettingsDialogHeader`/`ThemeToggle` received (Y8-01/02/03/04).
2. **The single HIGH is a wrong-track race** (H3-01) — the only finding that can produce a user-visible correctness failure (playback reverting to the wrong track under rapid clicking).
3. **Dead/dormant subsystems inflate the surface.** The cache-monitoring UI (T4-01), `processingService` (A6-08), `RealTimeAnalysisStream`/`AnalysisExportService` (T4-02), and `playlistTransformer` (TC9-21) are all unmounted/unwired — several MEDIUM findings are latent bugs that only bite if this dead code is revived. This limits real-world blast radius today but is a false-coverage and future-landmine risk.
4. **Test suite is broad but has pockets of false-confidence tests** — no-assertion tests (TC9-02, TC9-04, TC9-06), tautological assertions (TC9-14), and mocks that encode the wrong contract (A6-01's `queueService` test) that pass regardless of the code being correct.
5. **Design-system and a11y findings are all incremental** — token/contrast/semantic-HTML polish, no systemic regression.

**Most impactful issues**: H3-01 (wrong-track race, the only HIGH), R2-03 (stale-track streaming state on rapid skip), P7-01 (compounding Web Audio node leak across a listening session), Y8-06 (sidebar section labels fail WCAG AA contrast).

---

## HIGH

### H3-01: `usePlayTrack` overwrites in-flight AbortController without aborting it — rapid track switches can play the wrong track
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:44-89`
- **Status**: NEW
- **Description**: `playTrack()` creates a new `AbortController` into `abortRef.current` on every call but never aborts the previous one first — unlike its siblings `usePlayEnhanced.playEnhanced` (`hooks/enhancement/usePlayEnhanced.ts:433-434`) and `usePlayNormal.playNormal` (`hooks/enhancement/usePlayNormal.ts:322-323`), which both call `core.abortRef.current?.abort()` immediately before assigning the new controller. If the user clicks play on track A then quickly on track B before A's `/api/player/queue` POST resolves, both fetches run to completion; whichever *resolves* last (not whichever was *issued* last) fires its `wsContext.send({ type: 'play_enhanced', ... })` last, potentially reverting playback to the older track.
- **Evidence**:
  ```ts
  // usePlayTrack.ts:44-48 — no abort of the prior controller
  const controller = new AbortController();
  abortRef.current = controller;   // previous controller silently dropped, never aborted
  ```
  vs `usePlayNormal.ts:322-323` / `usePlayEnhanced.ts:433-434`: `core.abortRef.current?.abort(); core.abortRef.current = new AbortController();`. The test suite (`__tests__/usePlayTrack.test.ts`) only covers single-call scenarios — no overlapping-invocation test.
- **Impact**: On any UI allowing quick click-through (library list, queue, search, "Play All"), variable network latency can leave the backend streaming a different (older) track than the one last clicked, with no error surfaced — the success toast even shows the losing track's title. Matches the "stale closure → wrong track" HIGH class.
- **Suggested Fix**: Abort the previous controller before creating the new one, mirroring the sibling hooks; add a regression test asserting only the second of two rapid `playTrack()` calls sends `play_enhanced`.

---

## MEDIUM

### C1-01: QueuePanel list key mixes array index into a memoized row's identity, defeating the memo it was built for
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:240-266`, `QueueTrackItem.tsx:38,119-137`
- **Status**: NEW
- **Description**: `QueuePanel` keys the drag-reorderable queue with `key={`${track.id}-${index}`}`. `QueueTrackItem` is `React.memo`-wrapped with a custom comparator specifically so hovering/dragging one row doesn't re-render siblings (per closed #4177). Because `index` is in the key, any reorder (`handleReorderTrack`) or mid-queue removal (`handleRemoveTrack`) changes the key of every shifted row; React unmounts and remounts those `<li>`/`QueueTrackItem` instances instead of diffing through the memo comparator — even though `track.id` is unchanged.
- **Evidence**: `QueuePanel.tsx:245` `key={`${track.id}-${index}`}`; memo comparator already checks `prev.index === next.index` (`QueueTrackItem.tsx:124-137`).
- **Impact**: Every drag reorder or mid-queue removal forces DOM remounts (and loses each row's internal `isFocused` state, `QueueTrackItem.tsx:38`) for all shifted rows — the opposite of what #4177 intended. Transient hover/focus UI on a shifting row is silently dropped.
- **Suggested Fix**: Key strictly by `track.id` (or a queue-entry UUID if a track can appear twice); pass `index` only as a prop.

### R2-01: errorTrackingMiddleware mislabels any slice's network-flavored error as a connection error and can resurrect a stale error after reconnect
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:69-122,278-287`; `connectionSlice.ts:48-61`
- **Status**: NEW
- **Description**: `categorizeError()` tags any message containing "network"/"connection"/"offline"/"timeout" as `NETWORK` regardless of originating slice; the middleware then forwards it into `connection.lastError` for `player/`, `queue/`, `cache/`, or `player/setStreamingError` actions alike. Because the forward is deferred to a microtask (`Promise.resolve().then(...)`), it can also land *after* a legitimate `setWSConnected(true)` (which synchronously clears `lastError`), resurrecting a stale unrelated error onto a freshly-reconnected connection.
- **Evidence**: keyword list at `:69-122`; forwarding at `:278-287`; `connectionSlice.ts:48-61` clears `lastError` on connect. Test only exercises `connection/setError` (guarded/never forwarded), so the cross-slice path is untested (see TC9-04).
- **Impact**: `connection.lastError` (read by `useAppErrors`/`useConnectionHealth`) can show a misleading "connection" error from an unrelated queue/cache/streaming failure, or flip back to error right after "reconnected". No live consumer today, so no visible symptom until either hook is wired into a status banner.
- **Suggested Fix**: Only forward genuinely connection-originated errors (tighten the NETWORK keyword set and/or gate on a network/WS action namespace), and make the forward synchronous (or cancelable) so it can't race a reconnect reset.

### R2-02: `reorderTrack` has no bounds validation — an out-of-range `fromIndex` inserts `undefined` into `queue.tracks`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:109-134`
- **Status**: NEW
- **Description**: Every other index-taking queue reducer validates its index (`removeTrack`, `setCurrentIndex`, `addTrack`); `reorderTrack` only short-circuits `fromIndex === toIndex`, then does `splice(fromIndex, 1)` + `splice(toIndex, 0, movedTrack)`. If `fromIndex >= tracks.length`, the first splice removes nothing, `movedTrack` is `undefined`, and the second splice inserts a literal `undefined`.
- **Evidence**: `queueSlice.ts:109-134` vs validated siblings at `:87-104`, `:167-178`, `:56-69`. Tests only cover in-range values.
- **Impact**: Any consumer assuming `Track` objects throws (`selectTotalQueueTime`/`selectQueueStats` do `track.duration`) or renders garbage. The action creator (`queueActions.reorderTrack` via `useQueue().reorder`) has no live caller today (real drag reorder goes through backend PUT + WS), so unreachable now — but one wiring change from exploitable by a bad index.
- **Suggested Fix**: Validate `0 <= fromIndex < tracks.length` and clamp/validate `toIndex`, no-op on out-of-range, matching the sibling reducers.

### R2-03: Streaming progress/complete/error reducers don't validate the update belongs to the active stream's `trackId`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:339-401`; `hooks/enhancement/useAudioStreamingCore.ts:169-301`; `types/ws/streaming.ts:67-84`
- **Status**: NEW
- **Description**: `startStreaming` stores a per-stream `trackId`, but `updateStreamingProgress`/`completeStreaming`/`setStreamingError` never compare against it. Incoming WS messages are filtered only by `stream_type` (`'enhanced'`/`'normal'`), and `AudioChunkMessage` has no `track_id` field to filter on. On rapid skip, `playEnhanced()` resets+starts streaming for the new track but sends no backend cancel first, so late chunks/end/error events for the previous track can be applied to the new track's streaming state.
- **Evidence**: `playerSlice.ts:339-401` (no trackId check); `useAudioStreamingCore.ts:172,282,295` (`stream_type` filter only); `types/ws/streaming.ts:67-84`; `usePlayEnhanced.ts:407-465` (no cancel-then-ack before new request).
- **Impact**: On a fast double/triple skip, a stale chunk-progress/end/error can misapply to the new track — wrong buffering %, premature "complete", or the old track's error on the new track. Real exposure bounded by the localhost cancel race window (small but not proven zero).
- **Suggested Fix**: Add `track_id` to chunk/end/error messages and drop non-matching ones in the handlers; or have the reducers accept+check `trackId` and no-op stale updates; or await a backend cancel-ack before `startStreaming`.

### M3-01: WebSocketProvider's `mountedRef` is never reset to `true`, freezing connection-status state after StrictMode remount
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:203,332-390,485-493`
- **Status**: NEW
- **Description**: `mountedRef = useRef(true)` is set to `false` in the mount-effect cleanup but never back to `true`. Under React 18 StrictMode (dev), the mount→cleanup→remount cycle leaves `mountedRef.current === false` permanently; the re-subscribed `open`/`close`/`error` handlers are all gated on it, so `isConnected`/`connectionStatus` freeze even though the singleton WS and `dispatchMessage` (not gated) keep working. `useAPIHealthPoll.ts:24` and `useArtworkUpdates.ts:116` handle this exact case by resetting the flag; WebSocketContext doesn't.
- **Evidence**: `:203`, gated handlers `:332-390`, effect `:485-493` never resets. Contrast `useAPIHealthPoll.ts:23-24`.
- **Impact**: Every `npm run dev` session, after the first-paint StrictMode double-invoke, connection-status UI shows stale/incorrect status for the rest of the page load even though playback/messaging work. Production Electron (StrictMode double-invoke disabled) unaffected — hence MEDIUM.
- **Suggested Fix**: Reset `mountedRef.current = true` at the top of the mount effect body before `connect()`.

### M3-02: `usePlaybackControl`'s return value is not memoized, defeating downstream memoization in ComfortableApp's keyboard-shortcut registration
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:326-338`; consumed at `ComfortableApp.tsx:65-82,228-229`
- **Status**: NEW
- **Description**: The hook memoizes each action via `useCallback` but returns a fresh object literal every render (no `useMemo`), unlike `usePlaybackQueue` (#2465) and the `useReduxState` hooks (#2537/#3619). `ComfortableApp` consumes the whole object in dependency arrays, so all four wrapping `useCallback`s churn every render, busting the `keyboardShortcutsArray` `useMemo` and re-registering all ~13 global shortcuts on every top-level render.
- **Evidence**: `usePlaybackControl.ts:326-338` (no `useMemo`); `ComfortableApp.tsx:65-82,228-229`.
- **Impact**: Wasted work (full shortcut re-registration) on every re-render of the ~300-line top-level component. Not a correctness break (register-by-key semantics), but an active violation of a pattern fixed three times elsewhere.
- **Suggested Fix**: Wrap the return in `useMemo` keyed on the individual callbacks.

### T4-01: Cache-monitoring API client's `SuccessResponse<T>` envelope never matches the actual backend wire shape
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:23-41,125-134,256,373-394`; `hooks/shared/useStandardizedAPI.ts:57-104`; backend `routers/cache_streamlined.py:80-98,171-205`
- **Status**: NEW
- **Description**: `request<T>()` blindly casts the body to `SuccessResponse<T>` (`data as SuccessResponse<T>`, no runtime check), and `isSuccessResponse()` gates consumers on `response.status === 'success'`. But `/api/cache/stats` returns a bare `CacheStatsResponse` and `/api/cache/health` a bare dict — neither has the `{status, data}` envelope (zero backend endpoints use `response_model=SuccessResponse[...]`), and `cache_health()` never returns the `timestamp` the frontend `CacheHealth` marks required. So `useCacheStats()`/`useCacheHealth()` always resolve `null` on a 200 OK.
- **Evidence**: `isSuccessResponse` always false against the real shape; consumers (`CacheStatsDashboard`, `CacheHealthMonitor`, `CacheHealthWidget`, `CacheManagementPanel`) render nothing/zero forever with no error.
- **Impact**: No live impact — all four consumers are unmounted (dead UI). But if revived, the whole cache-telemetry UI silently shows nothing while devtools show a "successful" response; existing #4310/#4302/#4187 discuss the dashboard without catching that it can never receive data.
- **Suggested Fix**: Either wrap the backend payloads in `SuccessResponse[...]`, or drop the envelope assumption and parse the bare shapes; replace the blind cast with a runtime shape check; reconcile the `timestamp` field.

### A6-01: queueService.getQueue() always returns an empty queue — array/object response-shape mismatch
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/queueService.ts:37-59`
- **Status**: NEW
- **Description**: `getQueue()` does `if (Array.isArray(result) && result.length) return result[0]; return {empty queue}`. `GET /api/player/queue` (`backend/routers/player.py:472-480`) returns a single `QueueInfoResponse` object, never an array, so `Array.isArray` is always false and it unconditionally returns the hardcoded empty queue, discarding the real response. The identical bug was fixed in `settingsService.getSettings()` (#3977) but never applied here. The unit test `queueService.test.ts:60` mocks `[mockQueueResponse]` (array-wrapped), encoding the wrong contract and masking the bug.
- **Evidence**: backend schema `player.py:154-165`; sibling fix `settingsService.ts:96-105`; test mock `:60`.
- **Impact**: No live caller today (`getQueue`/`setQueue` unused), but public API returning an always-empty queue with a green (wrong) test — latent, high-confidence-to-trigger.
- **Suggested Fix**: Handle both array and plain-object-with-`tracks` shapes as `settingsService` does; fix the test mock to the real object shape.

### A6-02: Shared `apiRequest` HTTP utility has no request timeout or retry logic
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:56-202`
- **Status**: NEW
- **Description**: `apiRequest()` (backing `libraryService`/`playlistService`/`settingsService`/`artworkService` and ad-hoc callers) calls `fetch()` with no internal `AbortController`/timeout and no retry — only forwarding a caller-supplied `signal` (rarely passed). The app's other two HTTP layers both implement a 30s timeout (`useRestAPI.ts:69-87`, `standardizedAPIClient.ts:195-196`), making this an inconsistency.
- **Evidence**: `apiRequest.ts:72-77` bare `fetch`; no `setTimeout(...abort)` in the file.
- **Impact**: A hung backend request (DB lock, stuck worker — documented failure modes) leaves the calling component's `loading` stuck `true` indefinitely with no recovery short of reload.
- **Suggested Fix**: Add a default internal timeout composing with any caller `signal`; consider bounded retry for idempotent GETs.

### A6-03: Bulk library actions have no in-flight guard — toolbar buttons stay clickable during batch requests
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/useBatchOperations.ts:45-122`; `Controls/BatchActionsToolbar.tsx:109-131`
- **Status**: NEW
- **Description**: `handleBulkAddToQueue/AddToPlaylist/Remove/ToggleFavorite` fire `Promise.allSettled` batches of N requests with no `isLoading`/re-entrancy guard, and the toolbar buttons have no `disabled` state tied to request progress.
- **Evidence**: `useBatchOperations.ts:45-60,106-122`; `BatchActionsToolbar.tsx:109-131` wires bare `onClick` with no `disabled`.
- **Impact**: Double-clicking "Remove"/"Toggle Favorite" (easy while a prior toast lingers) fires a second full batch concurrently — duplicate favorite flips (back to original) or duplicate queue insertions.
- **Suggested Fix**: Track `isSubmitting`, short-circuit re-entrant calls, and disable the buttons for the duration.

### A6-04: "Added to queue" success toast fires before the fetch that could fail
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:68-96`
- **Status**: NEW
- **Description**: `handleAddToQueue` calls `success(\`Added ${artist.name} to queue\`)` as the first statement in its `try`, before `await getArtistTracks(...)`. On fetch failure or empty result it then shows an error toast — after already claiming success. Sibling `handlePlayAll` correctly shows success last.
- **Evidence**: `:71-72` vs `handlePlayAll` `:32-66`.
- **Impact**: On any failure/empty-list for "Add artist to queue", user sees a false-positive success immediately followed by (or racing) an error toast.
- **Suggested Fix**: Move `success(...)` to after `queue.addMany(tracks)` succeeds.

### P7-01: AudioPlaybackEngine's GainNode is never disconnected — orphaned Web Audio nodes accumulate across track switches in enhanced-playback mode
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:94-104,298-309`; `hooks/enhancement/usePlayEnhanced.ts:206,275-293`
- **Status**: NEW
- **Description**: The constructor wires a `GainNode` permanently into the graph (`gainNode → analyser → destination`), but the class has no `dispose()` and `disconnectProcessor()` only tears down worklet/script nodes, never `gainNode.disconnect()`. In enhanced mode (`closeContextOnCleanup: false`) each track switch constructs a new engine and overwrites the ref without disconnecting the previous `gainNode`; since the shared analyser stays connected to `destination`, every prior track's `gainNode` is retained by the browser for the session. `usePlayNormal` avoids this via `closeContextOnCleanup: true`.
- **Evidence**: constructor `:95-102`, `disconnectProcessor` `:298-309` (gainNode untouched), `usePlayEnhanced.ts:289-293`. `gainNode.disconnect(` appears nowhere.
- **Impact**: Each enhanced-mode track change permanently strands one `GainNode` in the audio graph; per spec these aren't GC'd until the context closes (only on hook unmount, possibly hours in an Electron session). A multi-hour session accumulates a proportional, unbounded number of dangling nodes. Small per-node footprint, no audible glitch.
- **Suggested Fix**: Add `dispose()` calling `gainNode.disconnect()` and invoke it before overwriting `playbackEngineRef.current` and from `cleanupStreaming`.

### P7-02: `@mui/icons-material` imported via barrel (58 files) instead of per-icon paths
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: 58 files across `auralis-web/frontend/src/components/**` (e.g. `settings/ScanStatusCard.tsx:18`, `settings/SettingsTabNav.tsx:11`, `enhancement-pane/views/Expanded.tsx:2`)
- **Status**: NEW
- **Description**: 58 files import from the `@mui/icons-material` barrel (re-exports ~2,000 icon modules) vs the 10 that use the tree-shakable `@mui/icons-material/Icon` path form. MUI documents the barrel form as a perf footgun that slows Vite dev cold-start (esbuild pre-bundle scans the whole barrel) and production builds, and can leave more of the module graph in the chunk.
- **Evidence**: `grep "from '@mui/icons-material'"` → 58; `grep "from '@mui/icons-material/"` → 10.
- **Impact**: Slower `npm run dev` cold start and build times; potential larger main chunk. Lower priority for a localhost Electron bundle (no transfer cost) but still affects startup parse/eval and iteration speed.
- **Suggested Fix**: Convert the 58 to per-icon path imports; add a `no-restricted-imports` ESLint rule to prevent regression.

### P7-03: Album/track artwork always requested at full resolution, even for small thumbnails
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/artworkService.ts:58-61`; consumed at full-res by `components/library/Items/tracks/TrackRowAlbumArt.tsx:29` (40×40) and `components/shared/MediaCard/MediaCardArtwork.tsx:100-103`
- **Status**: NEW
- **Description**: `getArtworkUrl(albumId)` returns `/api/albums/{id}/artwork` with no size param; every consumer from a 40×40 thumbnail to a detail hero requests the same full-resolution image. `loading="lazy"` and explicit dimensions are correctly set (confirming #3993/#3956 not regressed), but on-screen thumbnails still decode full-res bitmaps.
- **Evidence**: `artworkService.ts:58-61`; `TrackRowAlbumArt.tsx:29` in a 40×40 container.
- **Impact**: In a virtualized library with hundreds of visible/recent thumbnails, the browser decodes and holds full-resolution bitmaps (decode CPU and per-image memory scale with source pixels, not CSS size). No network cost on localhost, but avoidable decode/memory overhead while scrolling.
- **Suggested Fix**: Add a `size`/`thumbnail` query param to the backend artwork endpoint and thread a size hint through `getArtworkUrl()`. Requires backend support — scope to backend-specialist.

### Y8-01: KeyboardShortcutsHelp close button has no accessible name
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/KeyboardShortcutsHeader.tsx:26-36`
- **Status**: NEW
- **Description**: The close `IconButton` renders only `<Close />` with no `aria-label`/`title`. Dialog is mounted globally in `ComfortableApp.tsx` and opened via `?`. Same pattern already fixed for `SettingsDialogHeader` (#4179) and the EnhancementPane close (#4208).
- **Impact**: Screen reader announces only "button" with no indication it closes the dialog.
- **Suggested Fix**: Add `aria-label="Close keyboard shortcuts"`.

### Y8-02: Top-bar search "clear" button has no accessible name
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/core/AppTopBarSearchInput.tsx:68-80`
- **Status**: NEW
- **Description**: The clear-search `IconButton` (rendered in the always-visible `AppTopBar` when a query is present) has only `<CloseIcon />` — no `aria-label`/`title`.
- **Impact**: Persistent, used on every search; screen reader users can't tell what the unlabeled button does.
- **Suggested Fix**: Add `aria-label="Clear search"`.

### Y8-04: Sidebar "New Playlist" trigger button has no accessible name
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/playlist/PlaylistList.tsx:191-217`
- **Status**: NEW
- **Description**: With `hideHeader` (sidebar usage via `SidebarContent.tsx:75`), the "New Playlist" trigger is a non-semantic `Box onClick` containing an icon-only `IconButton` (no `aria-label`) plus a sibling `<span>New Playlist</span>` not associated with the button.
- **Impact**: Tab lands on the inner button announced as bare "button"; the adjacent text isn't read as its name. Primary sidebar path to create a playlist.
- **Suggested Fix**: Add `aria-label="Create new playlist"`, or restructure the `Box` into a single `<button>` wrapping icon + text.

### Y8-06: Sidebar section labels ("Library", "Recently Played") likely fail WCAG AA contrast
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/layouts/Sidebar/SidebarStyles.ts:33-41`
- **Status**: NEW
- **Description**: `SectionLabel` sets `color: tokens.colors.text.disabled` (`rgba(255,255,255,0.40)`, documented as calibrated for the 3:1 *large-text* minimum only) at `fontSize.xs`, then applies an *additional* `opacity: 0.4` — effective alpha ≈ 0.16 against the dark glass sidebar, well under even 3:1, and the text is small (needs 4.5:1).
- **Evidence**: `SidebarStyles.ts:33-41`; token note `design-system/tokens/colors.ts:109`. Same class as fixed `MediaCardInfo` (#4182).
- **Impact**: The two persistent sidebar section headings are near-invisible for low-vision users and fail WCAG AA.
- **Suggested Fix**: Drop the extra `opacity: 0.4`; if more de-emphasis is wanted, use a token/size validated at ≥4.5:1 for small text.

### TC9-01: `apiRequest.ts` (core HTTP client) has zero direct tests and is fully mocked out in every service test
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:56-116` (no `utils/__tests__/apiRequest.test.ts`)
- **Status**: NEW
- **Description**: The single HTTP client used by all services has no test; all 8 service tests `vi.mock('@/utils/apiRequest')` wholesale, so the real 204 short-circuit (`:82`), error-body extraction `errorData.detail || errorData.message` (`:93-94`), non-JSON fallback (`:98-100`), and `APIRequestError` wrapping (`:103`) never execute.
- **Impact**: A regression in error-message/status/204 handling — the error surface for every failed API call — would be caught by no test.
- **Suggested Fix**: Add `utils/__tests__/apiRequest.test.ts` driving real `apiRequest()` against mocked `global.fetch` (200/JSON, 204, 4xx JSON, 4xx non-JSON, network reject).

### TC9-02: `errorTrackingMiddleware` `enabled` config flag is dead code, and the test meant to catch it has zero assertions
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:52,136,254,272`; test `__tests__/errorTrackingMiddleware.test.ts:403-426`
- **Status**: NEW
- **Description**: `ErrorTrackingConfig.enabled` (default `true`) is never read in a conditional — the "Log/Send if enabled" comments sit above `if (finalConfig.logToConsole)`/`if (finalConfig.logToServer)` (different flags). So `{ enabled: false }` still tracks/logs. The test "should respect enabled config" has zero `expect()` calls.
- **Impact**: No-assertion test passes regardless; the dead `enabled` flag silently no-ops for any caller trying to disable error tracking.
- **Suggested Fix**: Honor `finalConfig.enabled` (early-return) and assert it, or delete the flag; give the test a real assertion.

### TC9-03: WebSocketContext binary audio-chunk pairing (core of audio streaming) has zero test coverage
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:270-329`; only context test is `__tests__/WebSocketContext.reconnect.test.tsx`
- **Status**: NEW
- **Description**: The `audio_chunk_meta` → next binary frame pairing (`pendingAudioChunkMeta`, `instanceof ArrayBuffer/Blob`) is never exercised — the reconnect test only does `open`/`close`. Per-handler try/catch isolation is also untested.
- **Impact**: The whole audio-streaming pipeline depends on this pairing (same region as past bugs #3944/#4167); a regression (dropped/misordered pairing, unhandled Blob, meta-without-binary) would silently break playback uncaught.
- **Suggested Fix**: Add a test emitting a meta JSON frame then an ArrayBuffer, asserting a merged `audio_chunk`; add binary-without-meta and throwing-handler-isolation cases.

### TC9-04: Deferred network-error recovery re-dispatch is never exercised; its test passes trivially
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:278-287`; test `:300-321`
- **Status**: NEW
- **Description**: The NETWORK-error deferred `store.dispatch(connectionActions.setError(...))` for non-`connection/*` actions is never tested — the test dispatches `connection/setError` (excluded by the guard), so the assertion passes via the original reducer, not the recovery path; no microtask is awaited, and the dispatch spy is taken before `store` exists.
- **Impact**: False-confidence test; a regression breaking the user's WS/network auto-recovery would go undetected. (Behavioral counterpart of R2-01.)
- **Suggested Fix**: Dispatch a non-connection action producing a NETWORK error, `await Promise.resolve()`, assert `connectionActions.setError` via a real post-creation dispatch spy.

---

## LOW

### C1-02: Several actively-rendered components exceed the 300-line guideline
- **Severity**: LOW · **Dimension**: Component Quality · **Status**: NEW
- **Location**: `CozyAlbumGrid.tsx` (390L), `player/Player.tsx` (347L), `player/ProgressBar.tsx` (331L), `library/CozyLibraryView.tsx` (306L)
- **Description**: Live components over the CLAUDE.md 300-line limit, distinct from existing oversized-file issues #4292/#4297/#4301/#4077/#4078 (none under `components/`). Several other >300L files in these dirs (`TrackList.tsx`, `CacheHealthMonitor.tsx`, etc.) are confirmed dead/orphaned and excluded. `CozyAlbumGrid` bundles three components + two virtualization strategies.
- **Suggested Fix**: Split `CozyAlbumGrid` per component; extract `ProgressBar`'s touch/mouse/keyboard handlers into a `useProgressBarInteraction` hook. Batch with the #4075-4083 god-file split series.

### R2-04: `previousTrack` can set `queue.currentIndex` to -1 when `repeatMode === 'all'` and the queue is empty
- **Severity**: LOW · **Dimension**: Redux State · **Status**: NEW · **Location**: `store/slices/queueSlice.ts:203-218`
- **Description**: The wrap branch does `currentIndex = tracks.length - 1`; on an empty queue that's `-1`, violating the `0 <= currentIndex` invariant. Non-crashing today (selectors guard with `|| null`), but the stale `-1` persists after tracks are later added, so a track added to an empty repeat-all queue shows as "no current track".
- **Suggested Fix**: Guard with `tracks.length > 0`, e.g. `Math.max(0, tracks.length - 1)`.

### R2-05: `lastUpdated` invariant inconsistently maintained across slices
- **Severity**: LOW · **Dimension**: Redux State · **Status**: NEW · **Location**: `store/slices/cacheSlice.ts:106-115`, `connectionSlice.ts:125-127`
- **Description**: `player`/`queue` slices bump `lastUpdated` via `{reducer, prepare}` on every mutation; `cacheSlice.setIsLoading/setError` and `connectionSlice.setMaxReconnectAttempts` are plain reducers that skip it. No live consumer today, so latent; breaks if a "just refreshed"/staleness check keys off `lastUpdated`.
- **Suggested Fix**: Convert both to the `{reducer, prepare}` + `meta.timestamp` pattern used elsewhere in their files.

### L3-01: useQueueRecommendations logs its queue-size warning unconditionally on every render
- **Severity**: LOW · **Dimension**: Hook Correctness · **Status**: NEW · **Location**: `hooks/player/useQueueRecommendations.ts:122-130`
- **Description**: Warns when `queue.length > 1000` in the render body with no `_warnedRef` guard and no `import.meta.env.DEV` gate — fires every render and in production, unlike siblings `useQueueStatistics` (#3974) and `useQueueSearch` (#4194) whose completeness checks missed this third sibling.
- **Suggested Fix**: Apply the same `useRef` + `import.meta.env.DEV` guard.

### T4-02: Duplicated `any`-typed analysis payload interfaces (dead code)
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW · **Location**: `services/RealTimeAnalysisStream.ts:50,81`, `services/AnalysisExportService.ts:54,85`
- **Description**: Two structurally-identical interfaces each declare `spectrum.settings?: any` and `dynamics.loudness_war_assessment: any`. Neither service is imported outside its own tests (dead code). DRY violation + type holes if revived.
- **Suggested Fix**: When revived, share one typed interface and type both fields against the real backend payload; pairs with #4078.

### T4-03: `types/api.ts` retains unused Request/Response types drifted from the real backend
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW · **Location**: `types/api.ts:79-91,141-149,193-198`
- **Description**: `PlayerState`, `LibraryScanRequest` (`{directory?}` — real posts `{directories: [...]}`), `EnhancementSettingsResponse` (flat — real is nested `{message, settings}`) have zero importers and no longer match the backend, despite the file header claiming it maps to backend routers.
- **Suggested Fix**: Delete or correct to the current backend shapes.

### T4-04: `createCrudService()`'s generic `U`/`P` params bridged with an `unknown` double-cast
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW · **Location**: `utils/serviceFactory.ts:45-102`
- **Description**: Function-style endpoints pass the request body as `data as unknown as P` (`:86,99`), defeating type checking between body shape and URL-builder params. Dead path today (no consumer configures a function-style `create`/`update` with `P` ≠ `U`); landmine for the next one.
- **Suggested Fix**: Constrain `P` (e.g. `P extends Partial<U>`) or split "URL params" from "request body".

### T4-05: Caught exceptions repeatedly cast with `as Error` instead of `instanceof Error` narrowing
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW
- **Location**: ~9 files incl. `hooks/player/usePlayTrack.ts:83`, `hooks/fingerprint/useSimilarTracks.ts:227`, `utils/errorHandling.ts:90,477`, `performance/lazyLoader.tsx:188,235,325,330`, `hooks/shared/useOptimisticUpdate.ts:58`, `components/library/Details/useAlbumDetails.ts:81` + `useArtistDetailsData.ts:61`, `EditMetadataDialog/useMetadataForm.ts:79,158`
- **Description**: `(err as Error).name === 'AbortError'` asserts `err is Error` without checking; `catch` bindings are `unknown`. No crash today (only `.name` read → `undefined`), but a false guarantee for any future code reading more `Error` fields.
- **Suggested Fix**: Add a shared `isAbortError(e: unknown): e is DOMException` guard and reuse at all sites.

### D5-01: Brand accent hex `#7366f0` duplicated as a magic fallback instead of `tokens.colors.brand.primary`
- **Severity**: LOW · **Dimension**: Design System · **Status**: NEW · **Location**: `hooks/app/useArtworkPalette.ts:135`, `utils/colorExtraction.ts:283-293`
- **Description**: Both hardcode `#7366f0` (and its `r:115,g:102,b:240`) as the artwork-extraction fallback instead of importing `tokens.colors.brand.primary` (same value, `design-system/tokens/colors.ts:41`). Drifts silently if the brand is rebranded.
- **Suggested Fix**: Import tokens and use `tokens.colors.brand.primary`; derive r/g/b via the hex helper.

### D5-02: Four call sites reimplement hex→rgba conversion instead of the existing `withOpacity()` helper
- **Severity**: LOW · **Dimension**: Design System · **Status**: NEW · **Location**: `components/album/AlbumArt.tsx:51-56`, `components/shared/Toast/toastColors.ts:10-14`, `components/library/Items/tables/AlbumTrackTable.tsx:37`, `TrackTableHeader.tsx:12`
- **Description**: `design-system/tokens/with-opacity.ts` exports `withOpacity()` (used by 7+ files); these four locally reimplement the identical `parseInt(hex.slice...)` conversion. Inputs are token-derived (not bypasses), so a DRY/consistency issue.
- **Suggested Fix**: Replace all four with `withOpacity(token, alpha)`.

### D5-03: Off-token-scale magic font sizes
- **Severity**: LOW · **Dimension**: Design System · **Status**: NEW · **Location**: `components/settings/FoldersList.tsx:56,60`, `components/features/discovery/SimilarTracksFooter.tsx:16`
- **Description**: `0.9rem`/`0.75rem`/`0.7rem` don't land on the `tokens.typography.fontSize` scale — same class as fixed #3983/#4204, in uncovered files.
- **Suggested Fix**: Use `tokens.typography.fontSize.base`/`.xs`.

### D5-04: 15 test files use `../../` relative imports instead of the `@/` alias
- **Severity**: LOW · **Dimension**: Design System · **Status**: NEW
- **Location**: 15 test files incl. `services/__tests__/{queueService,settingsService,processingService,similarityService,artworkService}.test.ts`, `contexts/__tests__/WebSocketContext.reconnect.test.tsx`, `components/core/__tests__/AppShellLandmarks.test.tsx`, `components/library/__tests__/{useBatchOperations,useMetadataEditing}.test.ts`, etc.
- **Description**: Distinct from #4205 (which fixed 3 files at 4-level depth); this is a broader set at 2-level `../../` depth. Production (non-test) code has zero relative-import violations.
- **Suggested Fix**: Convert to `@/...` in one pass.

### A6-05: Retry-eligibility check matches error message substrings instead of the HTTP status code
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW · **Location**: `utils/errorHandling.ts:333-348`, used by `services/processingService.ts:246-261`
- **Description**: `isRetryableError` pattern-matches `error.message` for `'network'`/`'502'`/`'503'`/`'429'` etc. rather than inspecting `APIRequestError.statusCode`. Fragile — a backend detail string coincidentally containing `"502"` would retry a non-transient 4xx; no path to retry a transient error whose text lacks the hardcoded words.
- **Suggested Fix**: Check `(error as APIRequestError).statusCode` (retry ≥500 + 429), falling back to message matching only for raw network failures.

### A6-06: Primary API base URL has no env-var override, unlike the standardized client
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW · **Location**: `config/api.ts:9-14` vs `services/api/standardizedAPIClient.ts:412-417`
- **Description**: `API_BASE_URL`/`WS_BASE_URL` are hardcoded `localhost:8765` with no `VITE_API_URL` escape hatch, while `getAPIClient()` reads `import.meta.env.VITE_API_URL ?? API_BASE_URL`. Downgraded per desktop/localhost context; only matters if port 8765 is unavailable.
- **Suggested Fix**: Read `VITE_API_URL`/`VITE_WS_URL` in `config/api.ts` too.

### A6-07: Dead `useQuery`/`useMutation` wrappers don't filter AbortError before surfacing it
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW · **Location**: `hooks/api/useRestAPI.ts:354-422`
- **Description**: These unused wrappers `setError(...)` unconditionally in their catch blocks (`:369-370,410-413`), undoing the AbortError/StaleRequestError filtering done one layer down (#2467/#2439); `useQuery` also has no unmount guard. Dead code (real usages import `useQuery` from `@tanstack/react-query`).
- **Suggested Fix**: Delete the exports, or add the same `AbortError`/`StaleRequestError` guard.

### A6-08: `processingService.ts` (377 lines) has zero production consumers
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW · **Location**: `services/processingService.ts` (whole file)
- **Description**: Every export is imported only by its own test; the real processing UI (`useEnhancementParameters.ts`) uses raw `fetch`. Same "infrastructure with only test consumers" class as #4271, distinct file. 377 lines of retry/WS logic give false coverage signal.
- **Suggested Fix**: Confirm intent; delete if abandoned or wire into the enhancement pane.

### P7-04: Per-track cache lists render unvirtualized rows for a session-unbounded track count
- **Severity**: LOW · **Dimension**: Performance · **Status**: NEW · **Location**: `components/shared/CacheManagementPanel/TrackCacheList.tsx:45`, `components/shared/CacheStatsDashboard.tsx:207`
- **Description**: Both `.map()` one DOM row per cached track inside a fixed-height scroll container with no `useVirtualizer`, unlike `TrackList`/`QueuePanel`. Cache track count is bounded by disk size, can exceed 100. (Note: these components are currently dead UI — see T4-01.)
- **Suggested Fix**: Reuse the existing `useVirtualizer` pattern.

### P7-05: Track-list row components (`TrackTableRowItem`, `ArtistTrackRow`) are not memoized
- **Severity**: LOW · **Dimension**: Performance · **Status**: NEW · **Location**: `components/library/Items/tables/TrackTableRowItem.tsx:26-143`, `components/library/Views/ArtistTrackRow.tsx:21-89`
- **Description**: Neither is `React.memo`-wrapped, unlike `AlbumCard` (#4189/#3929) / `QueueTrackItem` (#4177), so every row re-renders on each play/pause tick. `AlbumTrackTable` is live (20-30+ tracks); `ArtistTrackRow`'s data source is stubbed `[]` (inert today).
- **Suggested Fix**: Wrap both in `React.memo` with a stable-props comparator.

### Y8-03: Settings "remove folder" button relies on `tooltip` prop only, no `aria-label`
- **Severity**: LOW · **Dimension**: Accessibility · **Status**: NEW · **Location**: `components/settings/FoldersList.tsx:65-72`
- **Description**: The destructive remove-folder `IconButton` passes `tooltip="Remove this folder"` (only sets `aria-describedby`, not an accessible name) but no `aria-label`. Same anti-pattern fixed for `ThemeToggle` (#3960).
- **Suggested Fix**: Add `aria-label={\`Remove folder: ${folder}\`}`, or make the `IconButton` primitive default `aria-label` from `tooltip`.

### Y8-05: Play/pause toggled via keyboard shortcut is not announced to screen readers
- **Severity**: LOW · **Dimension**: Accessibility · **Status**: NEW · **Location**: `components/player/PlaybackControls.tsx:127-212`, `hooks/app/useKeyboardShortcuts.ts:146`
- **Description**: The play/pause button swaps its `aria-label`, but there's no `aria-live` announcement of the transition — and Space can toggle playback from anywhere. Track *changes* are announced (#2362), play/pause *state* is not.
- **Suggested Fix**: Add an `aria-live="polite"` region announcing "Playing"/"Paused" on `isPlaying` transitions.

### Y8-07: Sidebar section labels are not semantic headings
- **Severity**: LOW · **Dimension**: Accessibility · **Status**: NEW · **Location**: `components/layouts/Sidebar/SidebarStyles.ts:33-41`, `SidebarContent.tsx:52,63`
- **Description**: `SectionLabel` = `styled(Typography)` with no `variant`, rendering `<p>` not a heading, so heading-navigation (NVDA/JAWS/VoiceOver "H" key) can't jump to "Library"/"Recently Played". Minor — the sidebar has a `<nav aria-label>` landmark.
- **Suggested Fix**: Give `SectionLabel` `variant="h2"` (or appropriate level), preserving visuals via `sx`.

### TC9-05: `loggerMiddleware` error catch/rethrow branch is untested
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `store/middleware/loggerMiddleware.ts:162-166,225-234`; test `:291-315`
- **Description**: "should handle errors in actions" asserts `expect(() => throwingAction()).toThrow()` on a standalone function — never dispatches through the store, so the middleware's catch→`console.error`→rethrow never runs.
- **Suggested Fix**: Dispatch a throwing action through the configured store; assert `console.error` + propagation.

### TC9-06: Three no-op tautological tests in `useWebSocketSubscription.test.ts`
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/websocket/__tests__/useWebSocketSubscription.test.ts:305-320,322-329,702-714`
- **Description**: Three "regression" tests only assert `expect(true).toBe(true)` (manual-unsubscribe / null-ref / rapid cycle) — false coverage for the manual-unsubscribe edge cases.
- **Suggested Fix**: Assert mock unsubscribe call counts / no-throw, or delete.

### TC9-07: `services/fingerprint/FingerprintCache.ts` (IndexedDB layer) has zero test coverage
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW (distinct from #4239) · **Location**: `services/fingerprint/FingerprintCache.ts:1-385`
- **Description**: 385-line IndexedDB cache (`init/get/set/has/delete/clear/getStats/cleanup`) with stale eviction (`:111`) and TTL sweep (`:325`) is entirely untested.
- **Suggested Fix**: Add `fake-indexeddb` tests for round-trip, stale eviction, TTL cleanup.

### TC9-08: `usePlaybackControl.play()` "no track selected" guard is never tested despite harness support
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/player/usePlaybackControl.ts:138-140`; test `:74-76,87-100`
- **Description**: The hook throws "No track selected" when no current track; the wrapper documents `seedTrack: null` to exercise it, but no test uses it (all `play()` tests seed a track).
- **Suggested Fix**: Add a `seedTrack: null` test asserting the guard.

### TC9-09: `useQueueSearch` `currentTrackOnly` filter is untested and is a self-admitted stub
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/player/useQueueSearch.ts:241-246`
- **Description**: The filter compares against `queue[0]` with a comment admitting it "we'll skip this check"; no test/caller sets `filters.currentTrackOnly` (dormant). If wired it would filter to index 0, not the current track.
- **Suggested Fix**: Remove the dormant/incorrect filter or complete it (use current index) and test it.

### TC9-10: `useAudioVisualization` decay loop and no-AudioContext polling branch are never exercised
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/audio/useAudioVisualization.ts:159-171,276-300`; test `:16-20,92-93`
- **Description**: `beforeEach` always pre-installs the global AudioContext/analyser (polling branch never runs) and statically mocks `isPlaying: true` (decay/fade-to-`DEFAULT_DATA` never runs).
- **Suggested Fix**: Add a no-context test (polling + cleanup) and an `isPlaying` false-toggle test (decay).

### TC9-11: `cacheSlice` per-track stripping (#3623/#3967) is not actually verified
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `store/slices/cacheSlice.ts:42-58,76-101`; tests `__tests__/cacheSlice.test.ts`, `deterministic-timestamps.test.ts`
- **Description**: The slice strips `tracks: {}` to bound state size, but every fixture already sets `tracks: {}`, so `toEqual` passes whether or not stripping runs.
- **Suggested Fix**: Dispatch `setCacheStats` with a populated `tracks` and assert it becomes `{}`.

### TC9-12: `queueSlice.addTrack` mid-queue position-insert branch is untested
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `store/slices/queueSlice.ts:56-69`; test `__tests__/queueSlice.test.ts`
- **Description**: `addTrack(track, position)` supports `splice(pos, 0, ...)` insert, but every test appends only. Plumbed through `useReduxState.ts:160` (dormant).
- **Suggested Fix**: Add a positional-insert test asserting order + `lastUpdated`.

### TC9-13: `playerSlice.updatePlaybackState` `streaming` merge branch not directly tested
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `store/slices/playerSlice.ts:270-273`; test `:186-216`
- **Description**: The `streaming` deep-merge in `updatePlaybackState` is only hit indirectly via the dedicated streaming actions; no test calls `updatePlaybackState({ streaming: {...} })` directly to confirm `normal`/`enhanced` sub-objects merge.
- **Suggested Fix**: Add a direct `updatePlaybackState({ streaming: { normal: {...} } })` test asserting the other substate is preserved.

### TC9-14: Misleading/tautological selector test — asserts a field the selector doesn't have
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `store/selectors/__tests__/selectors.test.ts:532-536`; source `store/selectors/index.ts:299-307`
- **Description**: "appSnapshot returns isReady=false when no track" only asserts `typeof snap === 'object'`; `selectAppSnapshot` has no `isReady` field — the name promises coverage that doesn't exist.
- **Suggested Fix**: Assert the actual snapshot fields for the empty-track state (or rename/fix).

### TC9-15: `useStandardizedAPI` (`useCacheHealth`/`useCacheStats`) auto-refresh is untested at both layers
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/shared/useStandardizedAPI.ts:81-101` (no test file)
- **Description**: This hook owns the auto-refresh interval for the cache dashboards; the skipped component test (`CacheHealthWidget.test.tsx:574`) defers it to "hook tests" that don't exist — untested at both levels. (The skip itself is #4264, not re-reported.)
- **Suggested Fix**: Add fake-timer hook tests asserting refetch-on-interval and clear-on-unmount.

### TC9-16: `useAPIHealthPoll` visibility-pause/resume and fetch-failure branches untested
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/shared/useAPIHealthPoll.ts:37-64` (no dedicated test)
- **Description**: Extracted from `ConnectionStatusIndicator` (#4186) with past ordering/cleanup-race bugs (#3585); its only indirect coverage stubs an always-resolving `fetch`. No test drives `document.hidden`/`visibilitychange` or a rejecting fetch.
- **Suggested Fix**: Add a `document.hidden` toggle test and a rejecting-fetch test.

### TC9-17: `EnhancementInspectionLayer/*` (745 lines, interactive) has zero tests
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `components/enhancement/EnhancementInspectionLayer/` (5 files, no `__tests__/`)
- **Description**: Mounted in production via `EnhancementPane.tsx`. `PresetSelector.tsx` has dropdown state + click-outside `useEffect` + keyboard handling (`:17-93`); `PlaybackControls.tsx` has error dismiss (`:93-101`). No tests.
- **Suggested Fix**: Add tests for `PresetSelector` (open/select/click-outside/Escape) and `PlaybackControls` error dismiss.

### TC9-18: Missing `act()` wraps in ~half of `usePlayerControls.test.ts`
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `hooks/player/__tests__/usePlayerControls.test.ts` (~54,63-87,156-202)
- **Description**: Many tests `await result.current.play()/.pause()` without `act(async …)` though `executeControl` does `setIsLoading`/`setLastError`. Assertions check return values, so they don't currently fail; `usePlayerControls` also has zero production consumers (nil real risk today).
- **Suggested Fix**: Wrap state-mutating hook calls in `act(async () => …)` consistently.

### TC9-19: `test/mocks/websocket.ts` `mockWSMessages` is dead and drifted from real message types
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `test/mocks/websocket.ts:147-285`
- **Description**: Exported but unused; references types absent from the real `WebSocketMessageType` union (`processing_*`, `connection_status`, `library_update` vs real `library_updated`, wrong `track_changed` shape). A future author copying these writes tests against non-existent contracts.
- **Suggested Fix**: Delete `mockWSMessages` or regenerate from the real union.

### TC9-20: `MockWebSocket.send()` throws for any non-OPEN state (real WebSocket only throws on CONNECTING)
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `test/mocks/websocket.ts:47-51`
- **Description**: Per WHATWG, `send()` while `CLOSING`/`CLOSED` is a silent no-op; only `CONNECTING` throws. This mock throws unconditionally when not `OPEN`, misrepresenting real behavior — a latent trap.
- **Suggested Fix**: Throw only on `CONNECTING`; no-op on `CLOSING`/`CLOSED`.

### TC9-21: `playlistTransformer.ts` is orphaned, untested, and disconnected from the real playlist data path
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `api/transformers/playlistTransformer.ts:1-65` (no test)
- **Description**: Its docstring claims it fixes #2505, but it has zero consumers besides the barrel; the live UI uses snake_case `Playlist` from `playlistService.ts` and reads `playlist.track_count` directly, not the camelCase `trackCount` the transformer produces. Dead code masquerading as a shipped fix.
- **Suggested Fix**: Wire it into the real service path and test it, or delete it and confirm #2505's actual fix lives in `playlistService`.

### TC9-22: `fireEvent` used for simple click/confirm interactions instead of `userEvent`
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW · **Location**: `components/library/__tests__/ArtistDetailView.test.tsx:128,135,142,153,160,168,169`; `components/player/__tests__/ClearQueueDialog.test.tsx:33,40,49,56`
- **Description**: These use `fireEvent.click` (no `userEvent`) for click/confirm flows incl. the destructive "Clear queue" confirm/cancel, bypassing realistic focus/pointer sequencing. (Overall ratio is healthy 107:250; `SearchBar.test.tsx`'s `fireEvent.input` is a deliberate #3614 choice, not a defect.)
- **Suggested Fix**: Migrate the two named files to `userEvent.setup()` + `await user.click(...)`.

---

## Relationships & Shared Root Causes

- **Sibling-fix drift (root cause of ~10 findings)**: H3-01, M3-02, L3-01, A6-01, Y8-01/02/03/04, D5-03, P7-05 are all "the one place a prior fix didn't reach." A completeness sweep when closing sibling issues (grep the fix pattern across the directory) would prevent this recurring class. The prior tickets' "Completeness Checks" sections explicitly missed the third sibling in the useQueue* case (L3-01).
- **errorTrackingMiddleware cluster**: R2-01 (behavioral cross-slice mislabel/race), TC9-02 (dead `enabled` flag + no-assertion test), and TC9-04 (untested deferred recovery) all sit in the same 300-line file. Fixing R2-01 should be paired with rewriting the three weak tests so the corrected behavior is actually verified.
- **Cache-monitoring dead subsystem**: T4-01 (envelope mismatch → always `null`), TC9-15 (auto-refresh untested), P7-04 (unvirtualized cache lists) all describe the same unmounted UI (`CacheStatsDashboard`/`CacheHealthMonitor`/`CacheHealthWidget`/`CacheManagementPanel`). One decision — revive-and-fix or delete — resolves all three plus existing #4310/#4302/#4187.
- **Rapid-skip / abort-race pair**: H3-01 (missing abort in `usePlayTrack`) and R2-03 (no `trackId` guard on streaming reducers) are two independent facets of the same "rapid track switch → wrong/stale track" hazard; both should be addressed for a robust fast-skip experience.
- **HTTP-layer inconsistency**: A6-02 (no timeout/retry in `apiRequest`), A6-06 (no env override), A6-05 (message-string retry classification), and TC9-01 (untested `apiRequest`) all stem from `apiRequest.ts` being the least-hardened of the three parallel HTTP layers. Consolidating toward one hardened client (or backporting the `standardizedAPIClient` hardening) resolves the cluster.
- **Dead-code false-coverage theme**: A6-08, T4-02, TC9-21, and much of the cache subsystem are unwired modules whose tests give false confidence — a tech-debt audit disposition (delete vs wire-in) would shrink the audit surface materially.

## Prioritized Fix Order

1. **H3-01** (HIGH) — abort-before-replace in `usePlayTrack`. Smallest change, only user-visible correctness bug (wrong track). One-line fix + regression test; mirror the sibling hooks.
2. **R2-03** — guard streaming reducers by `trackId` (pair with H3-01 for a complete fast-skip fix). Needs a small backend/message change or reducer-level check.
3. **P7-01** — add `AudioPlaybackEngine.dispose()` + call it on track switch/cleanup. Compounding leak during the app's primary playback mode.
4. **Y8-06** — drop the doubled sidebar-label opacity (WCAG AA fail on persistent nav headings). Trivial CSS fix.
5. **errorTrackingMiddleware cluster** — R2-01 + TC9-02 + TC9-04 together: fix the cross-slice forwarding/race, honor/remove `enabled`, and rewrite the three weak tests.
6. **A6-01** + **A6-04** + **A6-03** — user-facing feedback correctness (empty queue, false-success toast, double-submit); small, localized.
7. **Sibling-fix drift batch** — M3-02, L3-01, Y8-01/02/03/04, D5-01/02/03, P7-05, T4-05: mechanical, low-risk, high count; do as one grep-driven sweep.
8. **HTTP-layer hardening** — A6-02/05/06 + TC9-01: consolidate `apiRequest` toward the hardened client and add its missing tests.
9. **Dead-code dispositions** — T4-01/02/03/04, A6-07/08, TC9-21, P7-04, cache subsystem: decide delete-vs-wire-in (route to a tech-debt session; several map to existing #4271/#4310/#4302/#4187).
10. **Remaining test-quality gaps** — TC9-03/05..20, C1-01/02, R2-02/04/05, M3-01, P7-02/03: opportunistic.

---

*Generated by the frontend audit (9 dimensions, deep). Deduplicated against 183 frontend-labeled issues and cross-dimension overlaps. To publish as GitHub issues: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-07-12.md`*
