# Frontend Audit Report — 2026-02-12

**Auditor**: Claude Opus 4.6
**Scope**: `auralis-web/frontend/src/` — React 18 + TypeScript + Vite + Redux Toolkit + MUI 5
**Stats**: 286 components, 51 hooks, 16 services, 4 Redux slices, 127 test files (2,623 tests)

---

## Executive Summary

9 new findings across 7 audit dimensions. The most impactful issues are: (1) factory selectors that defeat React-Redux memoization causing excessive re-renders, (2) a units mismatch bug that makes playback drift correction permanently inactive, and (3) a useEffect cleanup leak in the WebSocket protocol hook that leaks event handlers on every unmount/remount.

Several existing issues from prior audits overlap with findings in this audit and are noted as duplicates where applicable.

---

## Deduplication Summary

Existing open issues checked against (60+ issues via `gh issue list`):

| Existing Issue | Relates To | Action |
|---|---|---|
| #2088 | No React error boundaries | SKIP — already tracked |
| #2098 | usePlayNormal wrong AudioContext sample rate | SKIP — already tracked |
| #2100 | usePlaybackControl non-existent sendMessage | SKIP — already tracked |
| #2104 | Dual streaming hooks | SKIP — already tracked |
| #2105 | PlayerStateData camelCase vs snake_case | SKIP — already tracked |
| #2115 | usePlayNormal time tracking interval never starts | SKIP — already tracked |
| #2116 | Volume scale inconsistency | SKIP — already tracked |
| #2117 | Dual WebSocket client systems | SKIP — related to F-03 but distinct |
| #2118 | Mock fingerprint data in production code | SKIP — already tracked |

---

## Findings

### F-01: Factory selectors return new object references on every call
- **Severity**: HIGH
- **Dimension**: Redux State / Performance
- **Location**: `auralis-web/frontend/src/store/selectors/index.ts:71-343`
- **Status**: NEW
- **Description**: All `makeSelect*` factory functions (e.g., `makeSelectPlaybackState`, `makeSelectFormattedTime`, `makeSelectQueueState`, `makeSelectConnectionStatus`) return plain functions that create new object literals on every invocation. They do NOT use `createSelector` from Reselect for memoization. When used with `useSelector(makeSelectPlaybackState())`, a new selector function is created on every render, and the selector returns a new object reference even if no state changed. This defeats React-Redux's reference equality check entirely.
- **Evidence**:
  ```typescript
  // store/selectors/index.ts:239-273
  export const makeSelectPlaybackState = () => (state: RootState): { ... } => {
    // Creates new object literal on EVERY call
    return {
      track: currentTrack,
      isPlaying,
      progress: duration > 0 ? currentTime / duration : 0,
      currentTime: formatSeconds(currentTime),
      duration: formatSeconds(duration),
      volume,
      isMuted,
      preset,
      canPlay: connected && currentTrack !== null,
    };
  };
  ```
- **Impact**: Components using these selectors re-render on EVERY Redux state change (including unrelated slices), even when their derived data hasn't changed. With 100ms position updates from usePlayerStreaming, this causes ~10 unnecessary re-renders/second across all connected components.
- **Suggested Fix**: Replace factory functions with proper `createSelector` from `@reduxjs/toolkit`. Use `useMemo` in components to ensure stable selector references: `const selector = useMemo(makeSelectPlaybackState, [])`.

---

### F-02: usePlayerStreaming drift threshold units mismatch
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStreaming.ts:258-281, 318-328`
- **Status**: NEW
- **Description**: The drift detection comparison uses mismatched units. `driftThreshold` is documented as milliseconds (default: 500 = "0.5 seconds"), but the `drift` variable is computed from `audioElement.currentTime` and `serverPosition`, both in **seconds**. The comparison `drift > driftThreshold` effectively requires `0.5 > 500` for a 500ms drift, which is always false. Drift correction never activates.
- **Evidence**:
  ```typescript
  // Line 83-84: Default is 500 (documented as "0.5 seconds")
  driftThreshold?: number; // Default: 500 (0.5 seconds)

  // Line 258: drift is in SECONDS (audioElement.currentTime is seconds)
  const drift = Math.abs(localPosition - serverPosition);

  // Line 262: Comparing seconds to milliseconds — always false for real drift
  if (drift > driftThreshold) { // 0.5 > 500 = false

  // Line 267: Would require 1000+ SECONDS of drift
  if (drift > 1000) { // never reachable
  ```
  Same bug at Layer 3 (line 328): `Math.abs(drift) > driftThreshold` — seconds vs milliseconds.
- **Impact**: Playback position drift between client and server is never detected or corrected. If the user seeks on another client or network latency causes desync, the progress bar and actual playback position diverge permanently until manual page refresh.
- **Suggested Fix**: Either convert `driftThreshold` to seconds (`driftThreshold / 1000`) before comparison, or convert `drift` to milliseconds (`drift * 1000`) before comparison. The former is simpler: `if (drift > driftThreshold / 1000)`.

---

### F-03: useWebSocketProtocol async IIFE cleanup never executes
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketProtocol.ts:57-95`
- **Status**: NEW
- **Description**: The `useEffect` at line 57 contains an async IIFE that returns a cleanup function at line 80-83 (inside the async body). However, `useEffect` only uses the synchronous return value for cleanup. The async IIFE returns a Promise, not a cleanup function. The actual synchronous cleanup at lines 92-94 is an empty function. This means `unsubscribeConnection()` and `unsubscribeError()` are never called on unmount.
- **Evidence**:
  ```typescript
  // Line 57-95
  useEffect(() => {
    if (autoConnect) {
      (async () => {
        try {
          const client = initializeWebSocketProtocol(url);
          const unsubscribeConnection = client.onConnectionChange(...);
          const unsubscribeError = client.onError(...);
          await client.connect();

          // This return is inside the async IIFE — useEffect never sees it
          return () => {
            unsubscribeConnection();
            unsubscribeError();
          };
        } catch (err) { ... }
      })();  // Returns Promise<void>, not cleanup function
    }

    return () => {
      // This is the actual cleanup — it does nothing
    };
  }, [autoConnect, url, onConnectionChange, onError]);
  ```
- **Impact**: Every mount/unmount cycle (component re-render, page navigation) accumulates leaked event handlers on the WebSocket client. Over time, stale handlers fire and dispatch state updates to unmounted components, causing React warnings and potential memory leaks.
- **Suggested Fix**: Move unsubscribe references to `useRef` and clean them up in the synchronous cleanup function. Alternatively, restructure to not use async IIFE — call `client.connect()` without awaiting in the effect body and store cleanup refs synchronously.

---

### F-04: useWebSocketSubscription manual unsubscribe re-subscribes instead of unsubscribing
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:77-82`
- **Status**: NEW
- **Description**: The function returned by `useWebSocketSubscription` (intended for manual unsubscription) calls `manager.subscribe()` instead of calling the unsubscribe function returned by `subscribe()`. This creates a duplicate subscription instead of removing the existing one.
- **Evidence**:
  ```typescript
  // Line 76-83
  return () => {
    const manager = getWebSocketManager();
    if (manager) {
      // BUG: This SUBSCRIBES again instead of unsubscribing
      manager.subscribe(messageTypes, memoizedCallback);
    }
  };
  ```
- **Impact**: Any code calling the returned unsubscribe function creates a duplicate subscription, doubling message processing. The automatic cleanup via `useEffect` (line 73) works correctly, so this only affects code that manually calls the return value. Impact is limited since the hook docstring discourages manual use.
- **Suggested Fix**: Store the unsubscribe function from the effect's `manager.subscribe()` call in a ref and return it, or simply return a no-op since automatic cleanup handles it.

---

### F-05: Hardcoded color values bypass design tokens
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: Multiple files (see below)
- **Status**: NEW
- **Description**: 30+ hardcoded hex color values found in component files, bypassing the design token system at `design-system/tokens.ts`. Some are standalone hardcoded values, some are used as CSS variable fallbacks, and some create color palettes outside the design system.
- **Evidence**:
  Files with hardcoded colors:
  - `components/shared/MediaCard/MediaCardArtwork.tsx:39-43` — 5 standalone gradient colors (`#667eea`, `#764ba2`, `#f093fb`, etc.)
  - `components/library/Controls/BatchActionsMoreMenu.tsx:43` — `#1a1f3a`, `#0A0E27`
  - `components/enhancement-pane/sections/AudioCharacteristics/AudioCharacteristics.tsx:29-30` — `#3B82F6`, `#26de81`
  - `components/library/Styles/Color.styles.ts:53,128,130` — `#7366F0`, `#26de81`, `#ff9500`
  - `components/player/QueueStatisticsPanel.tsx:251-256,458` — 4 fallback colors
  - `components/player/QueueRecommendationsPanel.tsx:496,511,569` — 3 fallback colors
  - `components/player/QueuePanel.tsx:527,570` — 2 fallback colors
  - `components/album/AlbumArt.tsx:67,69` — `#FFB800`
- **Impact**: Theme switching (dark/light) will show inconsistent colors. Design system changes require hunting through individual components. Some of these colors have no semantic meaning and cannot be maintained centrally.
- **Suggested Fix**: Move gradient palettes and accent colors to `tokens.ts`. Replace fallback patterns (`tokens.colors.accent.primary || '#0066cc'`) with just the token (tokens should never be undefined). Extract `Color.styles.ts` values to tokens.

---

### F-06: 6 production components exceed 300-line guideline
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: See list below
- **Status**: NEW
- **Description**: Project guidelines specify components should be under 300 lines. Six production component files significantly exceed this limit:
  1. `AlbumCharacterPane.tsx` — 1,099 lines (3.7x limit)
  2. `EnhancementInspectionLayer.tsx` — 740 lines (2.5x limit)
  3. `CacheManagementPanel.tsx` — 694 lines (2.3x limit)
  4. `QueueRecommendationsPanel.tsx` — 663 lines (2.2x limit)
  5. `QueueSearchPanel.tsx` — 657 lines (2.2x limit)
  6. `QueuePanel.tsx` — 630 lines (2.1x limit)
- **Impact**: Harder to maintain, test, and review. Increases cognitive load and merge conflict likelihood. Suggests these components have multiple responsibilities that should be decomposed.
- **Suggested Fix**: Extract sub-components for distinct visual sections within each oversized component. For example, `AlbumCharacterPane` likely contains separate sections (header, stats, controls, visualizations) that could each be their own component.

---

### F-07: Minimal ARIA/accessibility attributes across components
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/` (global)
- **Status**: NEW
- **Description**: Only 20 of 286 component files (7%) contain any ARIA attributes, `role`, or `tabIndex`. Critical custom controls like the audio player progress bar, volume slider, and playback controls have minimal screen reader support. There is no skip navigation link, no focus trapping in modals/drawers, and no screen reader announcements for player state changes.
- **Evidence**:
  - `ProgressBar.tsx` has 8 ARIA instances (best coverage) — includes `role="slider"`, `aria-valuemin/max/now`
  - `PlaybackControls.tsx` has 7 — includes `aria-label` on buttons
  - `QueuePanel.tsx` has 8 — includes `role="listbox"`
  - `VolumeControl.tsx` has only 2 ARIA instances
  - 266 component files have ZERO ARIA attributes
  - No `aria-live` regions for player state announcements
  - No keyboard navigation for queue management (drag-and-drop only)
- **Impact**: Application is not usable with screen readers. Custom controls are invisible to assistive technology. Keyboard-only users cannot access many features. WCAG 2.1 Level AA compliance is not met.
- **Suggested Fix**: Prioritize ARIA for player controls (progress bar, volume, play/pause state), queue management (list navigation), and library browsing (data grids). Add `aria-live="polite"` region for "Now playing" announcements. Implement keyboard navigation for queue reordering.

---

### F-08: usePlaybackQueue callbacks recreated on every state change
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:236-542`
- **Status**: NEW
- **Description**: Multiple `useCallback` hooks include `state` (the full queue state object) in their dependency arrays. Since `state` changes on every WebSocket message (queue updates, shuffle changes, repeat mode changes), these callbacks are recreated on every state change. Any child component receiving these callbacks as props will re-render unnecessarily.
- **Evidence**:
  ```typescript
  // Line 274: setQueue depends on full state
  }, [api, state]);

  // Line 447: toggleShuffle depends on state.isShuffled
  }, [api, state.isShuffled]);

  // Line 501: setRepeatMode depends on full state
  }, [api, state]);

  // Line 542: clearQueue depends on full state
  }, [api, state]);
  ```
  The `state` dependency is needed for optimistic rollback (capturing `previousState`), but the pattern causes excessive callback recreation.
- **Impact**: Components using `setQueue`, `setRepeatMode`, or `clearQueue` from this hook re-render every time any queue state changes (including position updates and WebSocket syncs that may happen frequently).
- **Suggested Fix**: Use `useRef` to track the latest state for rollback instead of including `state` in callback dependencies. Pattern: `const stateRef = useRef(state); stateRef.current = state;` then use `stateRef.current` for rollback capture inside callbacks.

---

### F-09: Zero test coverage for all hook modules
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/` (all subdirectories)
- **Status**: NEW
- **Description**: There are 51 custom hooks across 8 subdirectories (player, enhancement, websocket, api, library, app, fingerprint, shared) with **zero** direct test files. No `.test.ts` or `.test.tsx` files exist anywhere under the `hooks/` directory. While some hooks are exercised indirectly through component tests, the critical hooks for player control, WebSocket communication, and audio streaming have no dedicated unit tests.
- **Evidence**:
  ```
  $ find auralis-web/frontend/src/hooks -name "*.test.*"
  (no results)
  ```
  Untested critical hooks include:
  - `usePlaybackControl` — playback commands
  - `usePlaybackQueue` — queue management with optimistic updates
  - `usePlayerStreaming` — drift correction (has the bug in F-02)
  - `useWebSocketProtocol` — connection lifecycle (has the bug in F-03)
  - `usePlayNormal` / `usePlayEnhanced` — audio streaming
  - `useWebSocketSubscription` — message routing (has the bug in F-04)
- **Impact**: Hook bugs (F-02, F-03, F-04) went undetected because there are no tests exercising these code paths. Refactoring hooks risks introducing regressions with no safety net. The most complex and error-prone frontend code (audio streaming, WebSocket sync, optimistic updates) has the least test coverage.
- **Suggested Fix**: Create test files for at least the 6 critical hooks listed above. Use `renderHook` from `@testing-library/react` with mock WebSocket context and Redux store. Priority: `usePlayerStreaming` (drift logic), `useWebSocketProtocol` (cleanup), `usePlaybackQueue` (optimistic rollback).

---

## Dimension Checklists

### Dimension 1: Component Quality
- [x] Single responsibility — 6 components exceed 300 lines (F-06)
- [x] Prop drilling — minimal, Redux and context used appropriately
- [x] Conditional rendering — no reconciliation issues found
- [x] Key usage — stable keys used in list components
- [x] Ref usage — audio refs used correctly in player hooks
- [x] Error boundaries — only 2 exist, already tracked as #2088
- [x] Unmounted component updates — async operations in useRestAPI lack cancellation

### Dimension 2: Redux State Management
- [x] Slice design — 4 well-structured slices, normalized state
- [x] Selector memoization — factory selectors broken (F-01)
- [x] Dispatch ordering — websocketMiddleware dispatches are sequential, safe
- [x] Thunk/async error handling — errors caught and dispatched
- [x] Middleware — offline queue properly bounded (100 max)
- [x] State shape — reasonably flat, streaming nested in player but acceptable
- [x] Serializable state — non-serializable ignored for connection.lastError (documented)

### Dimension 3: Hook Correctness
- [x] Dependency arrays — stale state in usePlaybackQueue callbacks (F-08)
- [x] useEffect cleanup — WebSocket protocol hook leaks handlers (F-03)
- [x] useCallback/useMemo — callbacks recreated unnecessarily (F-08)
- [x] Custom hook return stability — useRestAPI return changes on isLoading change
- [x] Race conditions — drift correction units bug prevents any correction (F-02)
- [x] WebSocket hooks — cleanup leak (F-03), unsubscribe bug (F-04)
- [x] Player hooks — drift never corrected (F-02)
- [x] API hooks — no request cancellation on unmount in useQuery

### Dimension 4: TypeScript Type Safety
- [x] `any` usage — 53 instances across 15 files (moderate, mostly test mocks)
- [x] Type assertions — `as any` used in WebSocket message handlers (websocketMiddleware.ts:165-166)
- [x] API response types — standardizedAPIClient.ts has proper Zod schemas
- [x] WebSocket message types — discriminated via MessageType enum
- [x] Event handler types — properly typed
- [x] Union exhaustiveness — switch statements have default cases
- [x] Generic constraints — useRestAPI uses generic type parameters

### Dimension 5: Design System Adherence
- [x] Token usage — 30+ hardcoded colors found (F-05)
- [x] Spacing — tokens.spacing used consistently
- [x] Typography — tokens.typography used consistently
- [x] Responsive — breakpoints defined but limited usage
- [x] Dark/light theme — hardcoded colors break theme switching (F-05)
- [x] Import paths — `@/` absolute imports used consistently

### Dimension 6: API Client & Data Fetching
- [x] Error handling — HTTP errors caught and surfaced via ApiErrorHandler
- [x] Loading states — tracked per-hook via useState
- [x] Request cancellation — AbortController used for timeout but NOT for unmount
- [x] Retry logic — standardizedAPIClient has retry, useRestAPI does not
- [x] Response validation — Zod schemas in standardizedAPIClient, none in useRestAPI
- [x] Base URL — configurable via `VITE_API_BASE_URL` env var
- [x] camelCase/snake_case — handled in usePlayerStateSync, but inconsistent elsewhere (#2105)

### Dimension 7: Performance
- [x] Unnecessary re-renders — factory selectors cause excessive re-renders (F-01)
- [x] Large list rendering — not virtualized (potential issue for large libraries)
- [x] Bundle size — not analyzed (would require build)
- [x] Image optimization — artwork served via API with 1-year cache header
- [x] WebSocket message rate — 100ms position updates + selector re-renders (F-01)
- [x] Audio buffer memory — PCMStreamBuffer has 5MB cap, reasonable
- [x] Effect cascades — callback recreation chain in usePlaybackQueue (F-08)

### Dimension 8: Accessibility
- [x] Keyboard navigation — basic support in player controls, none in queue
- [x] ARIA labels — sparse, only 20/286 files (F-07)
- [x] Focus management — not implemented for modals/route changes
- [x] Screen reader — no live region for player state
- [x] Color contrast — not audited (would need visual inspection)
- [x] Semantic HTML — MUI provides good baseline

### Dimension 9: Test Coverage
- [x] Critical path coverage — hooks completely untested (F-09)
- [x] Mock correctness — test mocks exist for WebSocket and API
- [x] Async testing — component tests use async patterns correctly
- [x] User interaction testing — @testing-library user events used
- [x] Snapshot overuse — not observed, tests use assertions
- [x] Edge cases — empty/error/loading states tested in component tests
