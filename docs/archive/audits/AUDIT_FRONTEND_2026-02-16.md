# Frontend Audit — 2026-02-16

## Executive Summary

Comprehensive audit of the Auralis React frontend covering 9 dimensions: Component Quality, Redux State Management, Hook Correctness, TypeScript Type Safety, Design System Adherence, API Client & Data Fetching, Performance, Accessibility, and Test Coverage.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH     | 13 |
| MEDIUM   | 14 |
| LOW      | 3 |
| **Total NEW** | **32** |

Plus 8 existing issues confirmed/extended: #2139, #2222, #2272, #2275/#2250, #2115, #2258, #2285, #2162.

**Key themes:**
1. **Infinite re-render loops** — `useStandardizedAPI`, `usePlaybackQueue`, and `useQuery` all have unstable dependencies causing infinite fetch loops (root cause: `useRestAPI` instability #2285)
2. **Zero test coverage on critical paths** — `usePlayEnhanced` (audio streaming) and `usePlayerStateSync` (WebSocket-to-Redux bridge) have no tests; 40+ integration tests permanently `describe.skip`-ped
3. **Accessibility gaps** — No keyboard drag-and-drop for queue, no `aria-live` for track changes, `role="button"` without `onKeyDown`, missing `aria-pressed` on toggles
4. **Performance** — `useAudioVisualization` sends 60 `setState` calls/second; TrackList renders all tracks without virtualization; `ScriptProcessorNode` runs audio on main thread
5. **Production mock data** — `useLibraryData` falls back to fake placeholder tracks on network error

---

## Findings

### CRITICAL Severity

---

### F-01: usePlayEnhanced — the core audio streaming hook — has zero test coverage

- **Severity**: CRITICAL
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts` (no matching test file)
- **Status**: NEW
- **Description**: `usePlayEnhanced` manages the entire PCM audio streaming pipeline: 5 WebSocket subscriptions, PCMStreamBuffer lifecycle, AudioPlaybackEngine creation, Redux state sync, seek operations, and cleanup. It is called directly by `Player.tsx` and drives all audio output. No test file exists.
- **Impact**: The central audio playback path has zero automated regression protection. Bugs in chunk processing, seek state, or AudioContext creation are only caught manually.
- **Suggested Fix**: Create `hooks/enhancement/__tests__/usePlayEnhanced.test.ts` covering mount subscriptions, chunk accumulation, seek flow, disconnect cleanup.

---

### F-02: usePlayerStateSync — the WebSocket-to-Redux bridge — has zero test coverage

- **Severity**: CRITICAL
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts` (no matching test file)
- **Status**: NEW
- **Description**: Mounted at the app root via `PlayerStateSync`, this hook dispatches 9 Redux actions based on every incoming WebSocket `player_state` message. Any regression here silently corrupts player state for the entire UI.
- **Impact**: Field name mismatches, dropped dispatches, or type errors in the mapper break all player state for all components.
- **Suggested Fix**: Create tests that mock `useWebSocketContext` and verify each field path mapping.

---

### HIGH Severity

---

### F-03: rAF animation leak on unmount in AlbumCharacterPane

- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:59-104`
- **Status**: NEW
- **Description**: `usePlaybackWithDecay` starts a `requestAnimationFrame` loop when playback stops but the `useEffect` cleanup does not cancel the frame on component unmount. If the user navigates away during the decay animation, the rAF callback continues calling `setIntensity`/`setIsAnimating` on the unmounted component.
- **Evidence**:
  ```typescript
  useEffect(() => {
    if (!isPlaying && wasPlayingRef.current) {
      animationFrameRef.current = requestAnimationFrame(animateDecay);
    }
    // NO return () => cancelAnimationFrame(...) here
  }, [isPlaying]);
  ```
- **Impact**: "setState on unmounted component" warnings, potential memory leak from dangling rAF loop.
- **Suggested Fix**: Add cleanup: `return () => { if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current); };`

---

### F-04: errorTrackingMiddleware never connected to Redux store

- **Severity**: HIGH
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/index.ts:26-42`, `store/middleware/errorTrackingMiddleware.ts`
- **Status**: NEW
- **Description**: Like `loggerMiddleware` (#2231), `errorTrackingMiddleware` is defined but never imported or applied to the store. The entire error tracking, recovery dispatch for network errors, and `captureErrorToServer` are dead code.
- **Evidence**:
  ```typescript
  // store/index.ts — only uses getDefaultMiddleware()
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ serializableCheck: { ... } }),
  ```
- **Impact**: No Redux-level error tracking at runtime. Network error recovery logic is inoperable.
- **Related**: #2231 (loggerMiddleware same pattern)
- **Suggested Fix**: Import and `.concat(createErrorTrackingMiddleware({ logToConsole: true }))`.

---

### F-05: usePlaybackQueue initial fetch loops via unstable `api` dependency

- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:213-234`
- **Status**: NEW
- **Description**: The initial queue fetch `useEffect` has `[api]` as its dependency. `api` comes from `useRestAPI()` which produces a new reference on every render (#2285). This creates an infinite fetch loop for queue state.
- **Evidence**:
  ```typescript
  useEffect(() => {
    const fetchInitialQueue = async () => {
      const response = await api.get<QueueState>('/api/player/queue');
      ...
    };
    fetchInitialQueue();
  }, [api]);  // api changes every render
  ```
- **Impact**: Continuous repeated fetches of queue state, compounding #2285.
- **Related**: #2285 (root cause), #2284 (same pattern in useEnhancementControl)
- **Suggested Fix**: Use `useRef` to gate initial fetch: `if (hasFetchedRef.current) return;`

---

### F-06: useLibraryData intentionally omits fetchTracks from deps — stale closure risk

- **Severity**: HIGH
- **Dimension**: Hook Correctness / API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:294-298`
- **Status**: NEW
- **Description**: The auto-load effect intentionally omits `fetchTracks` from its dependency array. The comment acknowledges this is to avoid an infinite loop. However, `fetchTracks` closes over `offset`, so the effect always calls the version captured at mount with `offset = 0`.
- **Evidence**:
  ```typescript
  useEffect(() => {
    if (autoLoad) {
      fetchTracks();
    }
  }, [view]); // Only depend on view, not fetchTracks (to avoid infinite loop)
  ```
- **Impact**: After `loadMore` updates offset, a view change calls stale `fetchTracks` with wrong offset. The `autoLoad` prop change is silently ignored.
- **Suggested Fix**: Stabilize `fetchTracks` with a ref-based offset, then include it in deps.

---

### F-07: useStandardizedAPI infinite re-fetch with inline options objects

- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:96-153`
- **Status**: NEW
- **Description**: The `fetch` callback lists `options` (an object prop) as a `useCallback` dependency. Callers passing inline object literals create a new reference every render, causing `fetch` to be recreated, which triggers the `useEffect`, which calls `fetch()` — infinite loop.
- **Evidence**:
  ```typescript
  const fetch = useCallback(async () => { ... }, [endpoint, options]);  // options is object
  useEffect(() => {
    if (options?.autoFetch !== false) { fetch(); }
  }, [fetch, options?.deps]);
  ```
- **Impact**: Any consumer using inline options triggers infinite HTTP request loop.
- **Related**: #2284, #2285 (same class of bug — unstable deps)
- **Suggested Fix**: Destructure options primitives as deps: `[endpoint, method, timeout, cache]`.

---

### F-08: VITE_API_URL vs VITE_API_BASE_URL — two competing env var names

- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `hooks/api/useRestAPI.ts:18` vs `services/processingService.ts:102`, `hooks/enhancement/usePlayEnhanced.ts:524`
- **Status**: NEW
- **Description**: `useRestAPI` reads `VITE_API_BASE_URL`, everything else reads `VITE_API_URL`. Setting one env var in production will not configure the other.
- **Evidence**:
  ```typescript
  // useRestAPI.ts:18
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765';
  // processingService.ts:102
  this.baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8765';
  ```
- **Impact**: Staging/production deployments with custom backend URLs partially fail — `useRestAPI`-based hooks hit localhost while other services work correctly.
- **Suggested Fix**: Standardize on `VITE_API_URL` across the codebase.

---

### F-09: loadMockData fallback injects fake tracks in production on network error

- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:77-133,186-194`
- **Status**: NEW
- **Description**: On any network error fetching tracks, the hook falls back to `loadMockData()` which injects hardcoded placeholder tracks ("Bohemian Rhapsody", "Hotel California") with `https://via.placeholder.com` URLs into production state.
- **Evidence**:
  ```typescript
  } catch (err) {
    error('Failed to connect to server');
    if (view !== 'favourites') {
      loadMockData();  // Injects fake data in PRODUCTION
    }
  }
  ```
- **Impact**: Users see fake data that looks real on network failure. Mock data persists in Redux state.
- **Suggested Fix**: Remove mock data fallback entirely. Show error state with retry button.

---

### F-10: useAudioVisualization sends 60 setState calls/second flooding React render pipeline

- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/audio/useAudioVisualization.ts:167-221`
- **Status**: NEW
- **Description**: `updateVisualization` calls `setData(...)` with a new object on every `requestAnimationFrame` tick (60fps). No throttle, no equality check. The `AudioReactiveStarfield` component at the app root receives these updates, causing the background to re-render 60 times/second.
- **Impact**: 60 re-render cycles per second on the root component subtree during playback, competing with playback-critical rendering.
- **Suggested Fix**: Use `useRef` to track last-emitted values; only call `setData` when delta exceeds threshold (0.01). Cap to ~30fps.

---

### F-11: Player.tsx auto-advance handleNext has stale closure — missing from dependency array

- **Severity**: HIGH
- **Dimension**: Performance / Hook Correctness
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:229-244`
- **Status**: NEW
- **Description**: The auto-advance effect reads `handleNext` from closure but omits it from the dep array. `handleNext` is not wrapped in `useCallback`, so it closes over stale `currentQueueIndex` and `queueTracks` from the render when the effect was first created.
- **Evidence**:
  ```typescript
  useEffect(() => {
    if (isComplete && nearEnd && hasMoreTracks && !hasAutoAdvancedRef.current) {
      handleNext();  // stale closure!
    }
  }, [streamingState, wsCurrentTime, trackDuration, currentQueueIndex, queueTracks.length]);
  // handleNext NOT in deps ↑
  ```
- **Impact**: During auto-advance in long queues, `handleNext` references wrong `currentQueueIndex`, potentially loading the wrong track or double-incrementing.
- **Suggested Fix**: Wrap `handleNext` in `useCallback` with correct deps and add it to the effect's dep array.

---

### F-12: AudioPlaybackEngine uses deprecated ScriptProcessorNode with no AudioWorklet fallback

- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:282-303`
- **Status**: NEW
- **Description**: Uses `createScriptProcessor` (deprecated, removed from spec) unconditionally. Runs audio processing on the main thread, competing with React rendering. No AudioWorklet fallback despite docstring claiming it.
- **Impact**: Browsers will drop `createScriptProcessor`. Main-thread audio causes glitches during heavy UI interactions (queue opening, library scrolling).
- **Suggested Fix**: Implement AudioWorklet-based processor. Keep ScriptProcessorNode as legacy fallback only.

---

### F-13: TrackList renders all loaded tracks into DOM without virtualization

- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/TrackList.tsx:126-162`
- **Status**: NEW
- **Description**: `TrackList` renders every loaded track as a DOM node via flat `.map()`. Uses infinite scroll (IntersectionObserver) so DOM node count grows unbounded — 10,000+ nodes after scrolling a large library. `@tanstack/react-virtual` is an installed dependency (#2180 notes it's unused).
- **Impact**: Libraries with thousands of tracks degrade to unusable scroll performance.
- **Related**: #2180 (react-virtual installed but never imported)
- **Suggested Fix**: Implement windowed rendering with `@tanstack/react-virtual`.

---

### F-14: WebSocket/streaming integration tests permanently skipped (describe.skip)

- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/websocket-realtime/websocket-realtime.test.tsx:31`, `streaming-audio/streaming-mse.test.tsx:441`
- **Status**: NEW
- **Description**: Two major integration test suites (20 tests each) — WebSocket lifecycle/state and streaming/MSE — are permanently `describe.skip`-ped. No CI config runs them separately. 5 additional service test suites are also skipped.
- **Impact**: 40+ integration tests covering the most critical paths never execute.
- **Suggested Fix**: Add `npm run test:integration` script with higher heap limit. Remove `describe.skip`.

---

### F-15: QueueTrackItem has no keyboard drag-and-drop or keyboard-accessible remove button

- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:281-332`
- **Status**: NEW
- **Description**: Queue items use HTML5 drag-and-drop without ARIA drag attributes or keyboard reorder support. The "Remove" button is conditionally rendered only on hover (`{isHovered && ...}`), invisible to keyboard users.
- **Impact**: Queue reordering and removal are completely inaccessible to keyboard-only and screen reader users.
- **Suggested Fix**: Always render remove button (use CSS opacity). Add keyboard reorder with Space/arrow keys per ARIA authoring practices.

---

### MEDIUM Severity

---

### F-16: TrackList role="button" items have no onKeyDown handler

- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/TrackList.tsx:128-137`
- **Status**: NEW
- **Description**: Track rows use `<div role="button" tabIndex={0}>` with `onClick` but no `onKeyDown` for Enter/Space activation. Keyboard users can focus but not activate tracks. Also uses incorrect `aria-selected` on `role="button"`.
- **Impact**: Keyboard-only users cannot play tracks from the library.
- **Suggested Fix**: Add `onKeyDown` handler for Enter/Space. Consider `role="option"` within `role="listbox"` container.

---

### F-17: updatePlaybackState Object.assign can clobber streaming sub-state

- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:233-248`
- **Status**: NEW
- **Description**: `Object.assign(state, action.payload)` with `Partial<Omit<PlayerState, 'lastUpdated'>>` still includes `streaming`. A server-sent `status_update` with a `streaming` field wipes client-side streaming progress.
- **Impact**: Progress bar resets mid-stream when server sends status_update with streaming field.
- **Suggested Fix**: Exclude `streaming` from the Omit type, or deep-merge the streaming sub-object.

---

### F-18: usePlayEnhanced fingerprint setTimeout not cleared on unmount

- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:486-493`
- **Status**: NEW
- **Description**: `handleFingerprintProgress` schedules a 2s `setTimeout` but never stores the timer ID. If the component unmounts within 2 seconds, the callback fires on a dead component.
- **Impact**: "setState on unmounted component" warning; potential stale state update.
- **Suggested Fix**: Store timeout in ref, clear in unmount cleanup.

---

### F-19: usePlaybackControl.play recreates on every position update via currentTrack object identity

- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:107-138`
- **Status**: NEW
- **Description**: The `play` callback lists `playbackState.currentTrack` as a dep. WebSocket `position_changed` messages arrive every second, potentially creating a new `currentTrack` object reference each time, recreating `play` and causing playback control re-renders during active playback.
- **Impact**: Playback controls re-render on every position update (~1/sec).
- **Suggested Fix**: Read track ID from a `useRef` instead of the dep array.

---

### F-20: usePlaybackState reads .track from messages that don't include it

- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:215-219`
- **Status**: NEW
- **Description**: `TrackLoadedMessage` has `data: { track_path: string }` and `TrackChangedMessage` has `data: { action: string }`. Neither includes a `track` field, but the handler reads `msg.data.track`. The `as` cast silences TypeScript.
- **Impact**: `msg.data.track` is always `undefined`; the hook silently misses track updates from these events.
- **Suggested Fix**: Remove the dead branch or update message types if backend sends a `track` field.

---

### F-21: Deprecated #667eea colour hardcoded in 3 files bypassing design tokens

- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `components/shared/Toast/toastColors.ts:31,51`, `components/library/Styles/Shadow.styles.ts:100-105`, `components/library/Views/ArtistTrackRow.tsx:37`
- **Status**: NEW (beyond #2135 which covers 8 other files)
- **Description**: Three files use `#667eea` / `rgba(102, 126, 234, ...)` — the deprecated pre-refactor aurora purple. The current brand accent is `#7366F0` per design tokens.
- **Impact**: Info toasts, player button shadows, and artist track row icons are visually off-brand.
- **Suggested Fix**: Replace with `tokens.colors.accent.primary` or `tokens.colors.semantic.info`.

---

### F-22: PlaylistList.tsx doubles px suffix on token spacing values causing broken CSS

- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/playlist/PlaylistList.tsx:193`
- **Status**: NEW
- **Description**: Token values are already strings like `'6px'`, but the template appends `px` again: `` `${tokens.spacing.sm}px ${tokens.spacing.md}px` `` produces `'6pxpx 12pxpx'`.
- **Impact**: Padding on playlist items is non-functional (browser ignores malformed value).
- **Suggested Fix**: Remove the extra `px`: `` `${tokens.spacing.sm} ${tokens.spacing.md}` ``

---

### F-23: processingService waitForCompletion polling timer never cancelled on unmount

- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/processingService.ts:382-406`
- **Status**: NEW
- **Description**: `setTimeout(poll, pollInterval)` handle is not stored. No way to cancel polling when calling component unmounts. The `onProgress` callback fires on unmounted components.
- **Impact**: Memory leak and "setState on unmounted component" after navigation during processing.
- **Suggested Fix**: Return a cancel function alongside the promise via AbortController pattern.

---

### F-24: handleScanFolder uses blocking alert()/prompt() instead of toast system

- **Severity**: MEDIUM
- **Dimension**: API Client / Component Quality
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:256-287`
- **Status**: NEW
- **Description**: Uses `prompt()` for folder path input and `alert()` for success/failure feedback, bypassing the toast notification system. Both are blocking and non-styleable.
- **Impact**: JS thread blocked during alert/prompt. Non-functional on many mobile browsers. Bypasses design system.
- **Suggested Fix**: Replace with controlled dialog and `success()`/`error()` from `useToast()`.

---

### F-25: 5+ files independently hardcode http://localhost:8765 fallback URL

- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/enhancement/usePlayEnhanced.ts:524`, `usePlayNormal.ts:422`, `services/processingService.ts:102`, `hooks/library/useInfiniteAlbums.ts:22`, `hooks/shared/useStandardizedAPI.ts:506`
- **Status**: NEW
- **Description**: Five files duplicate `import.meta.env.VITE_API_URL || 'http://localhost:8765'` instead of importing from the centralized `config/api.ts`. Adding auth headers or interceptors requires parallel changes.
- **Impact**: Configuration drift across API clients.
- **Suggested Fix**: Import from `@/config/api` everywhere.

---

### F-26: useRestAPI.get() error handler always reports status 500 for non-2xx responses

- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:86-87`, `types/api.ts:373-411`
- **Status**: NEW
- **Description**: `useRestAPI` throws a plain `Error` with status in the message string. `ApiErrorHandler.parse()` catches `Error` instances and hardcodes `status: 500`. A 404 is reported as 500.
- **Impact**: `ApiErrorHandler.isNotFound()` and `isUnauthorized()` always return false. Components cannot show "not found" vs "server error" appropriately.
- **Suggested Fix**: Throw `APIRequestError` (which carries status code) instead of plain `Error`.

---

### F-27: No aria-live region for track-change announcements in player

- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/TrackDisplay.tsx`, `Player.tsx:284`
- **Status**: NEW
- **Description**: When the current track changes, the title/artist update visually but no `aria-live` region announces the change. Screen reader users have no automated notification.
- **Impact**: Violates WCAG 2.1 SC 4.1.3 (Status Messages).
- **Suggested Fix**: Add `<div aria-live="polite" className="sr-only">Now playing: {title} by {artist}</div>`.

---

### F-28: Player.tsx orchestration component has zero direct test coverage

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx` (no matching test file)
- **Status**: NEW
- **Description**: `Player.tsx` wires all playback callbacks, manages auto-advance, and renders the player bar. `PlaybackControls.test.tsx` only tests the stateless button sub-component. The auto-advance stale closure (F-11) would only be caught by Player-level tests.
- **Impact**: Integration bugs between `usePlayEnhanced`, Redux queue, and playback callbacks are undetectable.
- **Suggested Fix**: Create `components/player/__tests__/Player.test.tsx` with Redux + WebSocket providers.

---

### F-29: Player tests use fireEvent instead of userEvent, bypassing real interaction semantics

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/player/__tests__/PlaybackControls.test.tsx`
- **Status**: NEW
- **Description**: All player tests use `fireEvent.click()` instead of `await userEvent.click()`. `fireEvent` dispatches synthetic events that skip pointer/mouse/focus sequencing and don't respect `disabled` attributes correctly.
- **Impact**: Tests may pass while actual user interactions fail, especially keyboard activation and disabled state.
- **Suggested Fix**: Replace `fireEvent.click` with `await userEvent.click` throughout player test suite.

---

### LOW Severity

---

### F-30: Shuffle/Repeat buttons missing aria-pressed toggle state

- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:141-201`
- **Status**: NEW
- **Description**: Shuffle and repeat mode buttons convey active state only via CSS styling. No `aria-pressed` attribute communicates the toggle state to assistive technology.
- **Impact**: Screen reader users cannot reliably determine shuffle/repeat state (WCAG 4.1.2).
- **Suggested Fix**: Add `aria-pressed={isShuffled}` and corresponding attributes to repeat buttons.

---

### F-31: 4 service tests permanently skipped with describe.skip

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `services/__tests__/artworkService.test.ts`, `queueService.test.ts`, `settingsService.test.ts`, `similarityService.test.ts`
- **Status**: NEW
- **Description**: All four service test files use `describe.skip(...)` with no mechanism to run them.
- **Impact**: Service-layer HTTP error handling and response parsing are untested.
- **Suggested Fix**: Remove `describe.skip` and use MSW-based mocking.

---

### F-32: playerSlice — the most frequently-mutated slice — has no dedicated reducer tests

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts` (no matching test file)
- **Status**: NEW
- **Description**: Only timestamp determinism is tested. The streaming state machine (`idle→buffering→streaming→complete→error`) and 15+ reducer actions have no unit tests.
- **Impact**: Reducer regressions (e.g., `resetStreaming` not clearing all sub-fields) go undetected.
- **Suggested Fix**: Create `store/slices/__tests__/playerSlice.test.ts` covering all action creators.

---

## Extends Existing Issues

| Issue | Extension |
|-------|-----------|
| #2139 | 6 NEW components over 300 lines including AlbumCharacterPane at 1099 lines |
| #2222 | Non-memoized selectors in `queueSlice.ts` shadow the memoized versions in `selectors/` |
| #2272 | Third duplicate `LibraryStats` interface in `useLibraryStats.ts` with different fields |
| #2275/#2250 | `coverUrl` dispatched for queue tracks too (line 119), not just currentTrack |
| #2115 | Root cause: `if (!playbackEngineRef.current) return` guard always exits (ref is null at mount) |
| #2258 | `usePlayEnhanced` has identical full-library fetch pattern (line 524) |
| #2285 | `useQuery` also enters infinite loop from unstable `api` object (line 282-299) |
| #2162 | Error fallback HTML also lacks ARIA landmarks / `role="alert"` for screen readers |

---

## Prioritized Fix Order

1. **F-07** + **F-05** (infinite re-fetch loops) — Fix alongside #2285 root cause
2. **F-09** (mock data in production) — Remove immediately, breaks user trust
3. **F-11** (auto-advance stale closure) — Wrong track plays in queue
4. **F-08** (env var mismatch) — Blocks deployment to non-localhost environments
5. **F-10** (60fps setState) — Highest continuous performance impact
6. **F-13** (TrackList no virtualization) — Unusable on large libraries
7. **F-01**, **F-02** (test coverage) — Must be established before fixing other bugs
8. **F-15**, **F-16** (keyboard accessibility) — WCAG compliance requirements
9. **F-12** (deprecated ScriptProcessorNode) — Browser compatibility risk
10. Remaining findings in severity order

---

## Cross-Cutting Recommendations

1. **Stabilize hook return values** — Every custom hook should ensure returned objects have stable references via `useMemo`/`useCallback` with correct deps
2. **Ban `any` in new code** — Set `noImplicitAny: true` in `tsconfig.json` for new files; use `unknown` as default generic parameter
3. **Wire up react-virtual** — The dependency is already installed; connect it to TrackList, AlbumGrid, and ArtistList
4. **Remove all mock data from production code** — Use MSW for development mocking, never in-app fallbacks
5. **Unskip integration tests** — Add `test:integration` npm script with 4GB heap; run in CI nightly
6. **Standardize env vars** — Single `config/api.ts` used everywhere, single `VITE_API_URL` env var
