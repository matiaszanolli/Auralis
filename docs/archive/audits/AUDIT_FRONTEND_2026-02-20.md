# Frontend Audit — 2026-02-20

**Scope**: React frontend — components, hooks, Redux state, WebSocket client, services, design system, types, API client
**Auditor**: Claude Sonnet 4.6 (automated)
**Methodology**: Full code trace of each dimension; findings disproved before inclusion; deduplication against 200+ open issues.

---

## Summary

| ID | Severity | Dimension | Status | Issue |
|----|----------|-----------|--------|-------|
| FE-01 | HIGH | Hook Correctness / Performance | NEW | #2486 |
| FE-02 | MEDIUM | Hook Correctness | NEW | #2487 |
| FE-03 | HIGH | Performance / API Client | NEW | #2488 |
| FE-04 | LOW | Hook Correctness | NEW | #2489 |
| — | HIGH | Component Quality | Existing: #2344 | — |
| — | HIGH | Hook Correctness | Existing: #2347 | — |
| — | HIGH | Accessibility | Existing: #2350 | — |
| — | HIGH | Redux State | Existing: #2178 | — |
| — | HIGH | API Client | Existing: #2478 | — |
| — | HIGH | Integration | Existing: #2263 | — |
| — | MEDIUM | Redux State | Existing: #2352 | — |
| — | MEDIUM | Redux State | Existing: #2255 | — |
| — | MEDIUM | Hook Correctness | Existing: #2294 | — |
| — | MEDIUM | Hook Correctness | Existing: #2177 | — |
| — | MEDIUM | WebSocket | Existing: #2281 | — |
| — | MEDIUM | WebSocket | Existing: #2117 | — |
| — | MEDIUM | Type Safety | Existing: #2280 | — |
| — | MEDIUM | Type Safety | Existing: #2276 | — |
| — | MEDIUM | Design System | Existing: #2356 | — |
| — | MEDIUM | Design System | Existing: #2357 | — |
| — | MEDIUM | Accessibility | Existing: #2362 | — |
| — | MEDIUM | Accessibility | Existing: #2136 | — |
| — | MEDIUM | Test Coverage | Existing: #2363 | — |
| — | MEDIUM | Test Coverage | Existing: #2364 | — |
| — | MEDIUM | Performance | Existing: #2176 | — |
| — | MEDIUM | Performance | Existing: #2258 | — |
| — | LOW | Type Safety | Existing: #2282 | — |
| — | LOW | Design System | Existing: #2233 | — |
| — | LOW | Test Coverage | Existing: #2367 | — |
| — | LOW | Performance | Existing: #2180 | — |
| — | LOW | Performance | Existing: #2148 | — |

---

## Dimension Coverage Notes

### Dimension 1: Component Quality

No **new** component-level findings. Known issues:
- `#2344` — `loadMockData` fallback injects fake tracks in production
- `#2139` — 6 production components exceed 300-line guideline
- `#2088` — No React error boundaries in frontend
- `#2176` — Index-based React keys on dynamic lists
- `#2175` — `PlaybackControls` uses imperative DOM style mutations for hover states
- `#2359` — `handleScanFolder` uses blocking `alert()`/`prompt()`

### Dimension 2: Redux State Management

4 Redux slices (player, queue, cache, connection). Selectors use `createSelector` (Reselect). No new state management bugs found beyond existing issues.

Known issues:
- `#2352` — `updatePlaybackState` `Object.assign` can clobber streaming sub-state
- `#2178` — `websocketMiddleware` NEXT/PREVIOUS reads stale state after dispatch
- `#2255` — `startStreaming` Redux action hardcodes intensity 1.0 in `usePlayEnhanced`

### Dimension 3: Hook Correctness

**TWO NEW findings** (FE-01, FE-02). Known issues:
- `#2294` — AudioContext resource leak in `usePlayEnhanced`
- `#2177` — `useOptimisticUpdate` execute callback has unstable dependencies
- `#2355` — `usePlaybackState` reads `.track` from messages that don't include it

### Dimension 4: TypeScript Type Safety

No new type-safety findings. Known issues:
- `#2280` — Dual `AudioFingerprint` interfaces with incompatible schemas
- `#2276` — `PlaybackState` interface mixes camelCase and snake_case fields
- `#2282` — `fingerprint_progress`/`seek_started` missing from canonical WebSocket types

### Dimension 5: Design System Adherence

Token system (`design-system/tokens.ts`) is comprehensive (818 lines, 800+ tokens). No new token violations discovered. Known issues:
- `#2356` — Deprecated `#667eea` colour hardcoded in toastColors, Shadows, ArtistTrackRow
- `#2357` — `PlaylistList.tsx` doubles `px` suffix on spacing tokens

### Dimension 6: API Client & Data Fetching

**ONE NEW finding** (FE-03). The `useRestAPI` hook has one new shared-state race condition (FE-04, LOW).

`useLibraryQuery` correctly uses abort controllers. `buildEndpoint` correctly parameterises all query options. `extractItemsFromResponse` correctly normalises snake_case → camelCase for albums.

Known issues:
- `#2478` — AudioPlaybackEngine buffer threshold inconsistent with `usePlayEnhanced` auto-start
- `#2258` — Streaming hooks fetch full library to find single track on every play

### Dimension 7: Performance

**ONE NEW HIGH finding** (FE-01 includes performance dimension). No additional new findings.

Known issues:
- `#2176` — Index-based React keys on dynamic recommendation and statistics lists
- `#2180` — `@tanstack/react-virtual` installed but never imported
- `#2258` — Full library fetch on every play

### Dimension 8: Accessibility

No new accessibility findings beyond existing ones.

Known issues:
- `#2350` — QueueTrackItem has no keyboard drag-and-drop or accessible remove button
- `#2351` — TrackList `role=button` items have no `onKeyDown` handler
- `#2362` — No `aria-live` region for track-change announcements
- `#2365` — Shuffle/Repeat buttons missing `aria-pressed` toggle state
- `#2136` — Sparse ARIA/accessibility attributes across frontend components

### Dimension 9: Test Coverage

Test suite has 132 files across all modules — good coverage of hooks, slices, and services. No new critical coverage gaps found.

Known issues:
- `#2363` — Player.tsx orchestration component has zero direct test coverage
- `#2364` — Player tests use `fireEvent` instead of `userEvent` bypassing real interaction
- `#2367` — `playerSlice` has no dedicated reducer unit tests

---

## Findings

### FE-01: `WebSocketProtocolClient.startHeartbeat()` Leaks a PONG Handler on Every Reconnect
- **Severity**: HIGH
- **Dimension**: Hook Correctness / Performance
- **Location**: `auralis-web/frontend/src/services/websocket/protocolClient.ts:265-289`
- **Status**: NEW

**Description**: `startHeartbeat()` is called inside `ws.onopen` (line 114) on every successful connection, including reconnections. Each call registers a new anonymous pong handler via `this.on(MessageType.PONG, () => { ... })` (line 284). The `on()` method adds to a `Set<MessageHandler>` keyed by message type. Since each call creates a **new anonymous function**, its reference is unique and is never deduplicated. `stopHeartbeat()` (lines 291-300) clears only the interval and timeout timers — **it never removes the pong handler**.

**Evidence**:

```typescript
// protocolClient.ts:265-289
private startHeartbeat(): void {
  this.heartbeatInterval = setInterval(() => {
    // ...
    this.send(MessageType.PING, {}, { priority: MessagePriority.CRITICAL }).catch(...)
    this.heartbeatTimeout = setTimeout(() => {
      if (this.isConnected()) this.ws?.close();
    }, 10000);
  }, 30000);

  // Handler registered on EVERY call — but NEVER removed by stopHeartbeat()
  this.on(MessageType.PONG, () => {
    if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
  });
}

private stopHeartbeat(): void {
  if (this.heartbeatInterval) { clearInterval(this.heartbeatInterval); this.heartbeatInterval = null; }
  if (this.heartbeatTimeout) { clearTimeout(this.heartbeatTimeout); this.heartbeatTimeout = null; }
  // ← MISSING: no cleanup of the PONG handler
}
```

After `N` WebSocket reconnections, `this.messageHandlers.get(MessageType.PONG)` holds `N` handlers. Each PONG message triggers all `N`. The accumulated handlers are never garbage-collected while the client object lives.

**Impact**: Progressive memory growth proportional to reconnect count. In a typical session with intermittent network drops (3–10 reconnects), the count is small. But in prolonged usage or flaky networks, this grows unboundedly. Additionally, every PONG response clears `this.heartbeatTimeout` `N` times (redundant but functionally harmless). Since `WebSocketProtocolClient` is a singleton (module-level `protocolClient` variable), the accumulation is application-lifetime.

**Suggested Fix**: Extract the pong handler into a named class method and call `this.messageHandlers.get(MessageType.PONG)?.delete(this.pongHandler)` inside `stopHeartbeat()`. Alternatively, store the unsubscribe function returned by `this.on()` and call it in `stopHeartbeat()`.

---

### FE-02: `useWebSocketSubscription` Inline Array Literals Cause Subscription Churn on Every Render
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:91-128` and callers
- **Status**: NEW

**Description**: `useWebSocketSubscription` has `[messageTypes]` as its `useEffect` dependency (line 128). Callers consistently pass **inline array literals** as the `messageTypes` argument. Each render creates a new array object with the same values — but `useEffect` uses `Object.is` for comparison, which fails for arrays. The effect therefore tears down and rebuilds the subscription on every single render of the calling component.

**Evidence**:

```typescript
// useWebSocketSubscription.ts:128
  }, [messageTypes]); // ← array reference changes every render

// usePlaybackState.ts:60-71 — new array literal on each render:
useWebSocketSubscription(
  ['player_state', 'playback_started', 'playback_paused', 'playback_stopped',
   'track_loaded', 'track_changed', 'position_changed', 'volume_changed'],
  (message) => { setState(prevState => { /* ... */ }) }
);

// useEnhancementControl.ts:136 — same pattern:
useWebSocketSubscription(
  ['enhancement_settings_changed'],
  (message) => { setState(prevState => ({ ... })) }
);
```

`usePlaybackState` calls `setState` inside the callback, causing a re-render on every WebSocket message. Since `position_changed` arrives every ~100ms, the subscription is torn down and rebuilt ~10 times per second. The `unsubscribeRef.current?.()` call at line 99 ensures only one subscription exists at a time, so no duplicate messages, but the constant subscribe/unsubscribe cycle creates unnecessary object allocations and manager overhead.

**Impact**: Subscription churn during active playback (~10 cycles/second for position updates). While no messages are dropped (the unsubscribe/resubscribe is synchronous), it creates runtime overhead and hinders profiler analysis. Any code that observes subscription counts (e.g., logging in `WebSocketContext.subscribe`) triggers proportionally.

**Suggested Fix**: Wrap `messageTypes` in `useMemo` inside `useWebSocketSubscription` to produce a stable reference, or document that callers MUST pass a stable array (via `useMemo` or module-level constant). The simplest fix is to use deep comparison (`JSON.stringify(messageTypes)` as a string dep) or memo inside the hook itself.

---

### FE-03: `AudioPlaybackEngine` Reuses Closed-Context `AnalyserNode` After Sample Rate Change — DOMException
- **Severity**: HIGH
- **Dimension**: Performance / API Client (Audio)
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:24-35` and `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:265-287`
- **Status**: NEW

**Description**: `AudioPlaybackEngine` stores a global `AnalyserNode` in `window.__auralisAnalyser` for the visualization hook. When `usePlayEnhanced` detects a sample rate change (e.g., switching from a 44.1 kHz track to a 48 kHz track), it closes the old `AudioContext` and creates a new one. A new `AudioPlaybackEngine` is then instantiated with the new context. However, `createGlobalAnalyser()` returns the existing `window.__auralisAnalyser` (which belongs to the now-**closed** old context). The engine then attempts to connect its `gainNode` (from the new context) to this stale analyser — a cross-context node connection that throws `DOMException: InvalidStateError`.

**Evidence**:

```typescript
// AudioPlaybackEngine.ts:24-35 — returns stale analyser from closed context:
function createGlobalAnalyser(audioContext: AudioContext): AnalyserNode {
  if ((window as any).__auralisAnalyser) {
    return (window as any).__auralisAnalyser;  // ← returns OLD context's analyser!
  }
  const analyser = audioContext.createAnalyser();
  (window as any).__auralisAnalyser = analyser;
  return analyser;
}

// AudioPlaybackEngine constructor:88-94
const analyser = createGlobalAnalyser(audioContext);  // audioContext = NEW context
this.gainNode.connect(analyser);              // gainNode from new context, analyser from CLOSED old context
analyser.connect(audioContext.destination);   // analyser from CLOSED old context → throws DOMException

// usePlayEnhanced.ts:269-279 — closes old context, creates new:
if (audioContextRef.current.sampleRate !== sourceSampleRate) {
  audioContextRef.current.close();  // ← OLD context closed here
  audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
}
// Then creates new AudioPlaybackEngine(audioContextRef.current, buffer)
```

Per the Web Audio API specification: "An InvalidAccessError MUST be thrown if source or destination is a node belonging to different AudioContexts."

**Impact**: Enhanced playback breaks on any track following a track with a different sample rate. The `AudioPlaybackEngine` constructor throws, leaving `playbackEngineRef.current = engine` pointing to a non-functional engine. No audio plays, and since the exception propagates through `handleStreamStart`, the streaming state is set to `error`. The user sees a stream error with no audio, persisting until a page reload. Mixed 44.1/48 kHz libraries (common in practice) trigger this on every cross-rate track switch.

**Suggested Fix**: In `createGlobalAnalyser()`, invalidate `window.__auralisAnalyser` when the passed `audioContext` differs from the context the stored analyser was created with. Store the context reference alongside the analyser: `window.__auralisAnalyserContext`. If they don't match, disconnect and recreate the analyser with the new context.

---

### FE-04: `useRestAPI` Shared `isLoading` State Prematurely Clears When Concurrent Requests are In-Flight
- **Severity**: LOW
- **Dimension**: Hook Correctness / API Client
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:23-25, 89-90, 120-122`
- **Status**: NEW

**Description**: `useRestAPI` exposes five methods (`get`, `post`, `put`, `patch`, `delete`) that all share a single `isLoading: boolean` state. Each method sets `isLoading=true` on entry and `isLoading=false` in its `finally` block. If two methods are called concurrently (e.g., `get()` for library data and `post()` for enhancement settings at the same time), the first method to complete sets `isLoading=false` — even though the second is still in flight. The UI then renders a "not loading" state prematurely.

**Evidence**:

```typescript
// useRestAPI.ts — shared state used by ALL 5 methods:
const [isLoading, setIsLoading] = useState(false);  // line 24

// get() — sets and clears independently:
const get = useCallback(async <T>(endpoint: string): Promise<T> => {
  setIsLoading(true);   // line 89 — can race with another method's setIsLoading(false)
  // ...
  finally { setIsLoading(false); }  // line 120-122 — clears even if post() is still pending
}, [...]);

// post() — same pattern, separate call:
const post = useCallback(async <T>(endpoint: string, ...): Promise<T> => {
  setIsLoading(true);   // line 143
  // ...
  finally { setIsLoading(false); }  // line 175
}, [...]);
```

For a component calling both `api.get('/api/library/tracks')` and `api.post('/api/player/volume', ...)` simultaneously, `isLoading` will be `false` as soon as the faster request completes.

**Impact**: UI loading spinners or disabled states tied to `isLoading` may flicker false-idle while the slower request is still in flight. Since most UI code uses `isLoading` from only one method at a time, this is low-impact in practice. Audits of existing hook usage show no component simultaneously issuing two different HTTP methods via the same `useRestAPI()` instance. Severity is LOW.

**Suggested Fix**: Replace the boolean `isLoading` with a counter: `const [pendingCount, setPendingCount] = useState(0)`. Increment at start, decrement in `finally`. Expose `isLoading: pendingCount > 0`.

---

## Previously-Confirmed Existing Issues (Not Re-Reported)

| Issue | Description |
|-------|-------------|
| #2478 | INT-02: AudioPlaybackEngine buffer threshold inconsistent with usePlayEnhanced auto-start |
| #2419 | No Subresource Integrity (SRI) on Google Fonts CDN links |
| #2384 | Scan progress current_file shows directory name (partially fixed for library router) |
| #2381 | Seek WebSocket message sends preset/intensity that backend silently discards |
| #2367 | playerSlice has no dedicated reducer unit tests |
| #2365 | Shuffle/Repeat buttons missing aria-pressed toggle state |
| #2364 | Player tests use fireEvent instead of userEvent |
| #2363 | Player.tsx orchestration component has zero direct test coverage |
| #2362 | No aria-live region for track-change announcements |
| #2359 | handleScanFolder uses blocking alert()/prompt() |
| #2357 | PlaylistList.tsx doubles px suffix on spacing tokens |
| #2356 | Deprecated #667eea colour hardcoded in toastColors, Shadows, ArtistTrackRow |
| #2355 | usePlaybackState reads .track from messages that don't include it |
| #2352 | updatePlaybackState Object.assign can clobber streaming sub-state |
| #2351 | TrackList role=button items have no onKeyDown handler |
| #2350 | QueueTrackItem has no keyboard drag-and-drop or accessible remove button |
| #2347 | AudioPlaybackEngine uses deprecated ScriptProcessorNode |
| #2344 | loadMockData fallback injects fake tracks in production on network error |
| #2294 | AudioContext resource leak in usePlayEnhanced |
| #2282 | fingerprint_progress and seek_started missing from WebSocket enum |
| #2281 | WebSocketProtocolClient correlation_id stripped by backend validation |
| #2280 | Dual AudioFingerprint interfaces with incompatible schemas |
| #2278 | Playlist created_at can be null but frontend requires string |
| #2277 | usePlayNormal not exported from enhancement hooks index |
| #2276 | PlaybackState interface mixes camelCase and snake_case |
| #2263 | Track artists/genres array-to-singular mismatch in frontend transformer |
| #2259 | Seek does not offset displayed time |
| #2258 | Streaming hooks fetch full library to find single track on every play |
| #2255 | startStreaming Redux action hardcodes intensity 1.0 |
| #2233 | Animation system has duplicate definitions and deprecated aliases |
| #2206 | WebSocket endpoint has no authentication |
| #2188 | Double crossfade: server applies crossfade then frontend does it again |
| #2180 | @tanstack/react-virtual installed but never imported |
| #2179 | CSS !important overrides in ViewToggle and ToastItem |
| #2178 | websocketMiddleware NEXT/PREVIOUS reads stale state after dispatch |
| #2177 | useOptimisticUpdate execute callback has unstable dependencies |
| #2176 | Index-based React keys on dynamic recommendation and statistics lists |
| #2175 | PlaybackControls uses imperative DOM style mutations for hover states |
| #2148 | tsconfig.json moduleResolution 'node' should be 'bundler' for Vite |
| #2139 | 6 production components exceed 300-line guideline |
| #2136 | Sparse ARIA/accessibility attributes across frontend components |
| #2135 | Hardcoded color values bypass design tokens in 8+ component files |
| #2118 | Mock fingerprint data in production code path |
| #2117 | Dual WebSocket client systems with incompatible message formats |
| #2106 | Backend pause destroys streaming task with no resume capability |
| #2088 | No React error boundaries in frontend |
