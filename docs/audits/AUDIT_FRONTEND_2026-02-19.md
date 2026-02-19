# Frontend Audit — 2026-02-19

## Executive Summary

Incremental audit of the Auralis React frontend (9 dimensions) following up on the 2026-02-16 comprehensive audit. Focused on component quality, state management, hook correctness, type safety, design system adherence, API client patterns, performance, accessibility, and test coverage.

**Findings by severity:**

| Severity | Count |
|----------|-------|
| HIGH     | 1 |
| MEDIUM   | 5 |
| LOW      | 1 |
| **Total NEW** | **7** |

Plus 1 existing issue extended: #2410.

**Key themes:**
1. **Type safety erosion** — 5 `useSelector((state: any) => ...)` calls bypass `strict: true`, and `RealTimeAnalysisStream` uses an undeclared class property
2. **WebSocket subscription churn** — `useWebSocketSubscription` memoization is a no-op, causing unsubscribe/resubscribe cycles on every parent render
3. **Hook return instability** — `usePlaybackQueue` returns a new object reference every render, cascading re-renders to all consumers
4. **API client fragmentation** — `processingService` bypasses the centralized `apiRequest` utility with 9 raw `fetch()` calls

---

## Findings

### HIGH Severity

---

### F-01: RealTimeAnalysisStream uses undeclared `this.isStreaming` class property

- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/services/RealTimeAnalysisStream.ts:224,544,555`
- **Status**: NEW
- **Description**: The class declares `private isConnected: boolean = false` (line 153) but never declares an `isStreaming` property. Despite this, `this.isStreaming` is assigned at lines 224, 544, and 555. With `strict: true` enabled in `tsconfig.json` (line 19), this should produce `TS2339: Property 'isStreaming' does not exist on type 'RealTimeAnalysisStream'`. The class already manages streaming state via `this.stateManager.setStreaming()` (lines 545, 556), so the undeclared property creates a phantom, disconnected state shadow.
- **Evidence**:
  ```typescript
  // Line 153 — only declared state property
  private isConnected: boolean = false;

  // Line 224 — undeclared property written in disconnect()
  disconnect(): void {
    this.isStreaming = false;  // TS2339: Property 'isStreaming' does not exist

  // Line 544 — undeclared property written in startStreaming()
  startStreaming(): void {
    this.isStreaming = true;   // TS2339
    this.stateManager.setStreaming(true);  // Proper state management exists

  // Line 529-530 — correct accessor via stateManager
  isStreamingData(): boolean {
    return this.stateManager.getStatus().isConnected && this.stateManager.getStatus().isStreaming;
  ```
- **Impact**: TypeScript compilation should fail. If the build bypasses this (e.g., `skipLibCheck`), the phantom `isStreaming` property diverges from `stateManager` truth, causing `isStreamingData()` to report incorrect state when only `stateManager.setStreaming()` is called without setting the phantom property (or vice versa).
- **Suggested Fix**: Either declare `private isStreaming = false;` and keep it synchronized with `stateManager`, or remove the phantom assignments and rely solely on `stateManager`.

---

### MEDIUM Severity

---

### F-02: 5 useSelector calls bypass strict TypeScript with `(state: any)`

- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `components/player/Player.tsx:70`, `components/enhancement/PlayerEnhancementPanel.tsx:71-72`, `hooks/enhancement/useEnhancedPlaybackShortcuts.ts:96`, `hooks/audio/useAudioVisualization.ts:134`
- **Status**: NEW
- **Description**: Five `useSelector` calls use `(state: any)` instead of the typed `RootState`, completely bypassing `strict: true` type checking. The `|| {}` fallback in Player.tsx additionally creates a new empty object reference when the player slice is falsy (though in practice the slice is always initialized).
- **Evidence**:
  ```typescript
  // Player.tsx:70 — any type + new object fallback
  const state = useSelector((state: any) => state.player || {});

  // PlayerEnhancementPanel.tsx:71-72 — two any selectors
  const streaming = useSelector((state: any) => state.player?.streaming || {});
  const currentTrack = useSelector((state: any) => state.player?.currentTrack);

  // useEnhancedPlaybackShortcuts.ts:96
  const streaming = useSelector((state: any) => state.player?.streaming || {});

  // useAudioVisualization.ts:134
  const streamingState = useSelector((state: any) => state.player?.streaming?.state);
  ```
- **Impact**: Property access errors (e.g., reading a renamed Redux field) are silently allowed at compile time but throw at runtime. Typed selectors exist in `store/selectors/` but are not used here.
- **Suggested Fix**: Replace `(state: any)` with `(state: RootState)` and use existing typed selectors from `store/selectors/playerSelectors.ts`.

---

### F-03: useWebSocketSubscription memoizedCallback is effectively a no-op — causes re-subscription on every parent render

- **Severity**: MEDIUM
- **Dimension**: Hook Correctness / Performance
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:79,110`
- **Status**: NEW
- **Description**: The hook attempts to memoize the incoming callback with `useCallback(callback, [callback])` (line 79). Since the dependency array contains the callback itself, the memoized version changes whenever the input changes — which is every render for inline callbacks. The `useEffect` at line 110 depends on `memoizedCallback`, so it unsubscribes and re-subscribes on every parent render. Multiple callers pass inline callbacks (`usePlaybackState` line 71, `useWebSocketLatestMessage` line 140), causing subscription churn on every WebSocket message during playback.
- **Evidence**:
  ```typescript
  // Line 79 — memoization with [callback] deps is a no-op for inline callbacks
  const memoizedCallback = useCallback(callback, [callback]);

  // Line 110 — effect re-runs every time memoizedCallback changes
  }, [messageTypes, memoizedCallback]);

  // Caller: usePlaybackState passes inline callback
  useWebSocketSubscription([...], (message) => {
    setState((prevState) => { ... });  // inline — new ref every render
  });
  ```
- **Impact**: During playback, `position_changed` messages arrive ~1/sec. Each triggers setState → render → new callback → unsubscribe + resubscribe. This creates ~1 teardown/rebuild cycle per second per subscription. With multiple WebSocket hooks active, this multiplies.
- **Suggested Fix**: Use a ref to track the latest callback instead of `useCallback`:
  ```typescript
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  // In effect: subscribe with (...args) => callbackRef.current(...args)
  ```

---

### F-04: usePlaybackQueue returns a new object reference on every render — cascading re-renders

- **Severity**: MEDIUM
- **Dimension**: Hook Correctness / Performance
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:558-578`
- **Status**: NEW
- **Description**: The hook returns a plain object literal containing `state`, `queue`, `currentTrack`, callback references, and loading/error state. No `useMemo` wraps the return value, so every state change (queue update, loading toggle, error) creates a new top-level object reference. Any consuming component that depends on the return object identity (e.g., in a `useEffect` dependency array or `useMemo`) will re-execute unnecessarily.
- **Evidence**:
  ```typescript
  // Line 558 — computed fresh every render
  const currentTrack = state.tracks[state.currentIndex] || null;

  // Lines 560-578 — new object literal, no useMemo
  return {
    state,
    queue: state.tracks,
    currentIndex: state.currentIndex,
    currentTrack,  // re-derived every render
    isShuffled: state.isShuffled,
    repeatMode: state.repeatMode,
    setQueue,
    addTrack,
    // ... 10 more fields
  };
  ```
- **Impact**: Every queue state change triggers re-renders in all components consuming `usePlaybackQueue`, even if the specific fields they use haven't changed.
- **Suggested Fix**: Wrap the return in `useMemo` with appropriate deps, or split into separate hooks for read-only state vs. mutation actions.

---

### F-05: processingService bypasses centralized apiRequest with 9 raw fetch() calls

- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/processingService.ts:196,231,249,268,294,317,331,345,359`
- **Status**: NEW
- **Description**: All other service files (`libraryService`, `playlistService`, `artworkService`, etc.) use the centralized `apiRequest.ts` utility which provides: consistent `APIRequestError` with status codes, 204 No Content handling, unified error logging, and a single base URL. `processingService` instead makes 9 direct `fetch()` calls with ad-hoc error handling (parsing JSON then throwing `new Error`), its own `this.baseUrl` property, and no centralized interceptors.
- **Evidence**:
  ```typescript
  // processingService.ts:268 — raw fetch, ad-hoc error handling
  const response = await fetch(`${this.baseUrl}/api/processing/job/${jobId}/download`);
  if (!response.ok) {
    const error = await response.json();  // Assumes JSON error body
    throw new Error(error.detail || 'Failed to download result');  // Plain Error, not APIRequestError
  }

  // Compare: libraryService.ts — uses centralized utility
  export async function getArtistTracks(artistId: number): Promise<ArtistTracksResponse> {
    return get<ArtistTracksResponse>(ENDPOINTS.ARTIST_TRACKS(artistId));
  }
  ```
- **Impact**: `processingService` errors don't carry HTTP status codes, bypass `ApiErrorHandler.isNotFound()`/`isUnauthorized()` checks (related to #2361), and won't benefit from any future centralized auth header injection or request logging.
- **Suggested Fix**: Refactor `processingService` to use `get()`, `post()`, `del()` from `apiRequest.ts`.

---

### F-06: useRestAPI has no hook-level AbortController for request cancellation on unmount

- **Severity**: MEDIUM
- **Dimension**: API Client / Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:51-67`
- **Status**: NEW
- **Description**: Each HTTP method (`get`, `post`, `put`, etc.) creates a local `AbortController` that only triggers on timeout (line 54). No hook-level controller exists that aborts in-flight requests when the component unmounts. After unmount, pending requests complete and call `setIsLoading(false)` and `setError(...)` on dead state.
- **Evidence**:
  ```typescript
  // Line 51-67 — AbortController scoped per-request, timeout-only
  const fetchWithTimeout = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
      try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        return response;
      } finally {
        clearTimeout(timeoutId);
        // No hook-level abort — controller is garbage collected
      }
    }, []
  );
  // No useEffect cleanup that calls controller.abort() on unmount
  ```
- **Impact**: Components that unmount during an active request (e.g., navigating away from library while fetching tracks) will have the request complete silently, wasting bandwidth. React 18 suppresses the "setState on unmounted component" warning but the resource waste remains.
- **Suggested Fix**: Maintain a `Set<AbortController>` via `useRef` at hook level. Add each new controller to the set, remove on completion. In a `useEffect` cleanup, abort all active controllers.

---

### LOW Severity

---

### F-07: Player.tsx volume useMemo includes unused `isStreaming` dependency

- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:249-251`
- **Status**: NEW
- **Description**: The `volume` memo computation only reads `state.volume` but includes `isStreaming` in its dependency array. This causes the memoized value to recalculate on every streaming state transition (idle → buffering → streaming → complete), even though the result is unchanged.
- **Evidence**:
  ```typescript
  // Line 249-251 — isStreaming not used in computation
  const volume = useMemo(() => {
    return state.volume ?? 50;
  }, [state.volume, isStreaming]);  // isStreaming is never read
  ```
- **Impact**: Minor — triggers 4 unnecessary recalculations per track lifecycle (one per streaming state transition). VolumeControl receives the same value but the memo cache is invalidated.
- **Suggested Fix**: Remove `isStreaming` from the dependency array: `[state.volume]`.

---

## Extends Existing Issues

| Issue | Extension |
|-------|-----------|
| #2410 | Player.tsx has 15 `console.log`/`warn`/`error` statements across all handlers (seek, play, pause, next, previous, volume, auto-advance). These are in user-action handlers (less frequent than the position_changed messages in #2410) but still produce debug noise in production. |

---

## Prioritized Fix Order

1. **F-01** (RealTimeAnalysisStream phantom property) — TypeScript error that should fail compilation; divergent state
2. **F-03** (WebSocket subscription churn) — Continuous performance impact during playback; affects all WebSocket hooks
3. **F-04** (usePlaybackQueue unstable return) — Cascading re-renders across queue consumers
4. **F-05** (processingService raw fetch) — Architecture drift from centralized error handling
5. **F-06** (useRestAPI no unmount cancellation) — Resource waste on navigation
6. **F-02** (useSelector `any` type) — Type safety erosion, risk of silent runtime errors
7. **F-07** (volume useMemo extra dep) — Minor performance cleanup

---

## Cross-Cutting Recommendations

1. **Stabilize WebSocket subscriptions** — Replace `useCallback(callback, [callback])` with a ref-based pattern across all subscription hooks
2. **Enforce typed selectors** — Add an ESLint rule to ban `useSelector((state: any) => ...)` and require `RootState` typing
3. **Memoize hook returns** — All custom hooks returning objects should use `useMemo` to prevent reference instability cascades
4. **Centralize API calls** — Migrate `processingService` to use `apiRequest.ts` utilities; consider deprecating direct `fetch()` in hooks
