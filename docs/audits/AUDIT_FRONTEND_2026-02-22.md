# Frontend Audit — 2026-02-22 (v2)

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: Two audit passes. Pass 1 used 3 parallel exploration agents (Components/Redux/Hooks, Types/Design/API, Performance/A11y/Tests). Pass 2 used 3 deeper agents (Hooks/Redux deep dive, Components/Design/A11y, TypeScript/API/Perf/Tests). All findings manually verified against source code. Cross-referenced against 61 existing issues (#2532–#2601).

## Executive Summary

The Auralis React frontend is in **excellent shape** after the recent batch fixes. Prior issues (#2532–#2558) addressing stale closures, WebSocket reconnection, React.memo correctness, and Redux churn have been properly fixed. The codebase demonstrates advanced patterns: ref-based stale closure prevention, counter-based loading states, sequence counters for race conditions, and comprehensive Reselect memoization.

Second pass found 4 additional issues missed by the first pass, primarily in the EnhancementContext and library data hooks.

**Results**: 9 confirmed findings (0 CRITICAL, 0 HIGH, 5 MEDIUM, 4 LOW). 18+ false positives eliminated across both passes.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 5 |
| LOW | 4 |

## Prior Findings Status (sample)

| Prior Finding | Issue | Status |
|--------------|-------|--------|
| TrackRow custom memo comparator ignores callbacks | #2540 | **FIXED** — uses default shallow React.memo with explicit comment (TrackRow.tsx:183-186) |
| usePlaybackState subscribes to position_changed | #2542 | **FIXED** — position_changed excluded, handled by dedicated usePlaybackPosition hook |
| 100ms setInterval fires when paused | #2543 | **FIXED** — short-circuit guard: `if (audioElement.paused && !audioElement.seeking) return` |
| usePlayEnhanced re-subscription loses messages | #2532 | **FIXED** — stable callback refs pattern (handleStreamStartRef etc.) |
| useRestAPI no AbortController on unmount | #2467 | **FIXED** — Set\<AbortController\> tracked + cleanup in useEffect return |
| usePlayEnhanced doesn't clear fingerprintTimeoutRef | #2536 | **FIXED** — clearTimeout in disconnect handler (lines 772-774, 818-820) |
| useReduxState returns new object every render | #2537 | **FIXED** — comprehensive createSelector memoization in selectors/index.ts |
| Track data duplicated across slices | #2534 | **FIXED** — normalized state, no duplication between playerSlice and queueSlice |

## Findings — Pass 1

---

### FE-11: Console.log/warn/error statements ship to production builds
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: 43 files across `src/components/` (55 instances) and `src/hooks/` (123 instances)
- **Status**: Existing: #2597
- **Description**: 178 console.log/warn/error statements exist in non-test source files with no build-time stripping configured. Vite config (`vite.config.mts`) has no `esbuild.drop` or terser `drop_console` setting. While most fire on user actions (low frequency), 39 are in hot-path streaming hooks (`usePlayEnhanced.ts`: 24, `usePlayNormal.ts`: 15) that execute during active audio playback, creating measurable I/O overhead.
- **Evidence**:
  ```
  Top offenders:
    usePlayEnhanced.ts:     24 statements (streams every audio chunk)
    Player.tsx:              17 statements (every UI interaction)
    usePlayerAPI.ts:         15 statements (every API call)
    usePlayNormal.ts:        15 statements (every normal playback action)
    useLibraryWithStats.ts:  14 statements (library data fetching)
  ```
  No stripping in Vite config:
  ```typescript
  // vite.config.mts — only has loader console.log, no production stripping
  // Missing: esbuild: { drop: ['console'] } or terser config
  ```
- **Impact**: Measurable performance overhead during audio streaming (24 log calls per chunk lifecycle in enhanced mode). DevTools console floods make debugging harder. Minor memory pressure from string formatting.
- **Suggested Fix**: Add `esbuild: { drop: ['console', 'debugger'] }` to Vite production config, or replace with a conditional logger utility that no-ops in production.

---

### FE-12: WebSocketContext propagates `any` types despite typed discriminated union
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:24,35,40,206,498`
- **Status**: Existing: #2598
- **Description**: The `WebSocketContext` defines its own `WebSocketMessage` interface (line 22) with `data?: any`, `current_track: any`, and `queue: any[]`. This shadows the well-typed `AnyWebSocketMessage` discriminated union in `types/websocket.ts` which defines 26 specific message types with proper type guards. All downstream consumers (hooks, components) receive `any`-typed data from the context, bypassing the type safety infrastructure.
- **Evidence**:
  ```typescript
  // WebSocketContext.tsx:22-26 — untyped transport layer
  export interface WebSocketMessage {
    type: string;
    data?: any;              // ← any
  }

  // WebSocketContext.tsx:35,40 — player state with any
  current_track: any;        // ← any
  queue: any[];              // ← any

  // WebSocketContext.tsx:206,498 — send function accepts any
  send: (message: any) => void;

  // types/websocket.ts — well-typed but unused by context
  export type AnyWebSocketMessage = PlayerStateMessage | AudioChunkMessage | ...;
  ```
  The `types/websocket.ts` file has comprehensive type guards (`isPlayerStateMessage`, `isAudioChunkMessage`, etc.) that cannot be leveraged because the context strips type information.
- **Impact**: Type errors in WebSocket message handling are not caught at compile time. Developers must manually cast or use type guards at every consumption point, leading to inconsistent safety.
- **Suggested Fix**: Replace the context's `WebSocketMessage` interface with `AnyWebSocketMessage` from `types/websocket.ts`. Type `send()` as `(message: OutgoingWebSocketMessage) => void`. This allows consumers to receive discriminated union types and use existing type guards.

---

### FE-13: Queue toggle button missing `aria-expanded` attribute
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:326-337`
- **Status**: Existing: #2599
- **Description**: The queue toggle button has `aria-label="Toggle queue"` (line 337) but is missing `aria-expanded={queuePanelOpen}` to communicate the panel's open/close state to screen readers. Toggle buttons that control expandable panels must have `aria-expanded` per WAI-ARIA 1.2.
- **Evidence**:
  ```tsx
  // Player.tsx:326-337 — missing aria-expanded
  <button
    onClick={() => setQueuePanelOpen(!queuePanelOpen)}
    // ... style props ...
    title="Toggle queue (Q)"
    aria-label="Toggle queue"
    // ← Missing: aria-expanded={queuePanelOpen}
  ```
- **Impact**: Screen reader users cannot determine whether the queue panel is open or closed. They hear "Toggle queue, button" but not the current state.
- **Suggested Fix**: Add `aria-expanded={queuePanelOpen}` to the button element. Optionally add `aria-controls="queue-panel"` with a matching `id` on the QueuePanel.

---

### FE-14: 5 player components exceed 300-line size guideline
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/`
- **Status**: Existing: #2600
- **Description**: Five components in the player directory significantly exceed the 300-line guideline documented in CLAUDE.md ("Components < 300 lines"):
  - `QueueSearchPanel.tsx`: 671 lines
  - `QueueRecommendationsPanel.tsx`: 663 lines
  - `QueuePanel.tsx`: 654 lines
  - `Player.tsx`: 548 lines
  - `ProgressBar.tsx`: 451 lines

  Additionally, `AlbumCharacterPane.tsx` in the library directory is 1,111 lines (3.7x guideline).

  Each file contains substantial inline style objects that inflate line count. The component logic itself is well-structured with proper hook delegation.
- **Impact**: Harder to maintain, review, and test. Higher cognitive load for new contributors. No functional impact.
- **Suggested Fix**: Extract inline style objects to separate `*.styles.ts` files (e.g., `QueuePanel.styles.ts`). This pattern would reduce component files by ~40-60% while keeping styles co-located.

---

### FE-15: No tests for usePlayEnhanced hook and AudioPlaybackEngine
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts`, `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts`
- **Status**: Existing: #2601
- **Description**: The `usePlayEnhanced` hook (the most complex hook in the codebase — handles WebSocket audio streaming, PCM buffer management, fingerprint-adaptive processing, and error recovery) has no dedicated test file. Similarly, `AudioPlaybackEngine` (Web Audio API buffer management) has no tests. Player hooks (`usePlaybackControl`, `usePlaybackQueue`, `usePlayerStreaming`) are well-tested, but the enhanced playback path — which is the primary differentiator of Auralis — is untested.
- **Impact**: Regressions in enhanced audio streaming (buffer underruns, chunk ordering, fingerprint integration) would not be caught by the test suite. The hook's complexity (24 console.log statements suggest extensive debugging was needed) makes it the most likely source of subtle bugs.
- **Suggested Fix**: Create `usePlayEnhanced.test.ts` covering: stream start/stop lifecycle, chunk queuing before stream_start, fingerprint timeout handling, error recovery, and cleanup on unmount.

---

## Findings — Pass 2

---

### FE-16: EnhancementContext silently swallows errors and accesses unvalidated response properties
- **Severity**: MEDIUM
- **Dimension**: API Client / Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/EnhancementContext.tsx:101,131,133-134,163,165-166`
- **Status**: NEW
- **Description**: Three related issues in the `EnhancementContext`:

  1. **Inconsistent error handling**: `setEnabled` re-throws errors (line 105), but `setPreset` (line 134) and `setIntensity` (line 166) silently catch and only log to console. Callers of `setPreset`/`setIntensity` have no way to know if the operation failed.

  2. **No error state**: The `EnhancementContextType` interface (line 17) exposes `isProcessing` but no `error` field. Even when operations fail, `isProcessing` returns to `false` (lines 136, 168), making the UI appear successful.

  3. **Unvalidated response access**: `data.settings.enabled` (line 101), `data.settings.preset` (line 131), and `data.settings.intensity` (line 163) are accessed without null-checking `data.settings`. If the backend returns `{ settings: null }` or an unexpected shape, this throws `TypeError`.

- **Evidence**:
  ```typescript
  // setEnabled — re-throws (line 105)
  } catch (error) {
    console.error('Failed to set enhancement enabled:', error);
    throw error; // ← Re-throws
  }

  // setPreset — silently swallows (line 134)
  } catch (error) {
    console.error('Failed to set enhancement preset:', error);
    // ← No throw — caller can't detect failure
  }

  // setIntensity — silently swallows (line 166)
  } catch (error) {
    console.error('Failed to set enhancement intensity:', error);
    // ← No throw — caller can't detect failure
  }

  // Unvalidated access (lines 101, 131, 163)
  setSettings(prev => ({ ...prev, enabled: data.settings.enabled }));
  // ← Throws TypeError if data.settings is null/undefined
  ```
- **Impact**: When `setPreset` or `setIntensity` API calls fail (network error, 500), the UI shows the spinner stopping (isProcessing=false) but the backend state didn't change. The user believes the operation succeeded. Additionally, if the backend returns an unexpected response shape, the TypeError is silently swallowed with no UI feedback.
- **Suggested Fix**: (1) Add `error` state to `EnhancementContextType`. (2) Make all three methods consistently re-throw or set error state. (3) Add null-check: `data?.settings?.enabled ?? prev.enabled`.

---

### FE-17: useLibraryData loadMore race condition with concurrent scroll events
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts:147-187`
- **Status**: NEW
- **Description**: The `loadMore` callback uses `isLoadingMore` state as a guard (line 148), but this value is captured by closure when the callback is created. Two rapid scroll events can both invoke `loadMore` before React re-renders, both seeing `isLoadingMore = false`. The `offsetRef.current` read/write at lines 155-156 is also non-atomic across concurrent calls.
- **Evidence**:
  ```typescript
  // useLibraryData.ts:147-187
  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) {   // ← STALE: both calls see false
      return;
    }

    setIsLoadingMore(true);            // ← React batches, doesn't update closure
    try {
      const limit = 50;
      const newOffset = offsetRef.current + limit;  // ← Both read same value
      offsetRef.current = newOffset;                // ← Both write same value
      setOffset(newOffset);

      // ... fetch with newOffset ...
      const transformedTracks = ...;
      setTracks(prev => [...prev, ...transformedTracks]); // ← Duplicate data appended
    }
  }, [isLoadingMore, hasMore, view]);
  ```
  Race sequence:
  1. Scroll event A: `isLoadingMore = false` (from closure) → enters function, calls `setIsLoadingMore(true)`
  2. Scroll event B (same frame): `isLoadingMore = false` (same closure, React hasn't re-rendered) → also enters function
  3. Both compute `newOffset = 0 + 50 = 50`, both fetch offset=50
  4. Both append the same page of tracks → duplicate data
- **Impact**: Rapid scrolling causes duplicate tracks in the library list view. The more common case — a single `loadMore` per render cycle — works correctly, but infinite scroll implementations can easily fire multiple events per frame.
- **Suggested Fix**: Replace `isLoadingMore` state guard with a ref: `const isLoadingMoreRef = useRef(false)`. Set `isLoadingMoreRef.current = true` synchronously before the async operation. This pattern is already used correctly in `useLibraryQuery` (`isFetchingMoreRef`).

---

### FE-18: usePlayNormal passes handlers directly to subscribe instead of using refs
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:443-458`
- **Status**: NEW
- **Description**: `usePlayEnhanced` uses the ref-indirection pattern (lines 697-703, 714-729) where callback refs are updated on every render and subscriptions call through refs: `(m: any) => handleStreamStartRef.current?.(m)`. This was specifically designed to fix #2532 (missed messages on WS reconnect). `usePlayNormal` instead passes handlers directly to `wsContext.subscribe()` (lines 443-458), bypassing the ref pattern.
- **Evidence**:
  ```typescript
  // usePlayEnhanced — ref indirection (safe, fix for #2532)
  handleStreamStartRef.current = handleStreamStart;  // Updated every render
  wsContext.subscribe('audio_stream_start',
    (m: any) => handleStreamStartRef.current?.(m)     // Always calls latest
  );

  // usePlayNormal — direct pass (fragile)
  unsubscribeStreamStartRef.current = wsContext.subscribe(
    'audio_stream_start',
    handleStreamStart as any    // Captures handler at subscription time
  );
  ```
- **Impact**: Currently safe because all handlers depend on stable values (`dispatch` from Redux, `cleanupStreaming` with `[]` deps). However, if any handler dependency changes in a future refactor, the subscriptions become stale until `playNormal()` is called again. The inconsistency between the two hooks creates a maintenance trap.
- **Suggested Fix**: Apply the same ref-indirection pattern from `usePlayEnhanced` to `usePlayNormal`: update `handleStreamStartRef.current = handleStreamStart` on every render, subscribe with `(m: any) => handleStreamStartRef.current?.(m)`, and move subscriptions to a `useEffect` with wsContext dependency.

---

### FE-19: Design system primitives use `{...(props as any)}` bypassing type safety
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/design-system/primitives/` (6 files)
- **Status**: NEW
- **Description**: Six design system primitive components spread rest props with `as any`, bypassing TypeScript checking on all passed-through props:
  - `Card.tsx:129`
  - `Slider.tsx:173`
  - `IconButton.tsx:177`
  - `Button.tsx:204`
  - `Badge.tsx:97`
  - `Input.tsx:187`
- **Evidence**:
  ```typescript
  // Card.tsx:129 — props are untyped
  <StyledCard
    variant={variant}
    padding={padding}
    hoverable={hoverable}
    selected={selected}
    {...(props as any)}   // ← TypeScript stops checking here
  >
  ```
- **Impact**: Invalid or misspelled props are accepted at compile time. IDE autocomplete doesn't work for rest props. MUI handles unknown props gracefully at runtime, so no crashes — but type safety is defeated for the most widely-used components.
- **Suggested Fix**: Type rest props using MUI's component prop types: `Omit<CardProps, 'variant' | 'padding' | ...>` to preserve type checking while allowing MUI-specific props through.

---

## False Positives Eliminated

### Pass 1

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| PerformanceMonitor-like unsynchronized state in hooks | React hooks run on main thread only — no concurrent access concern |
| Missing React.memo on 326 components | Most components are either leaf nodes, use Redux selectors (which memoize), or are rendered rarely. Only hot-path components need memo. |
| Stale closure in usePlayEnhanced fingerprint timeout | Timeout is properly cleared at lines 523-524, 772-774, 818-820 — fix for #2536 verified |
| Player.tsx creates new object reference every render (line 73) | Only 2 primitive selectors combined; the consuming component (VolumeControl) is memoized |
| Missing AbortController in API hooks | useRestAPI properly tracks active controllers in `Set<AbortController>` with unmount cleanup — fix for #2467 verified |
| camelCase/snake_case inconsistency | Centralized transformer layer exists at `src/api/transformers/` (track, album, artist, playlist). WS messages use inline mapping documented in types/websocket.ts |
| Missing focus trap in QueueSearchPanel | #2546 was addressed — has role="dialog", aria-modal, Escape key handler |
| useSelector without memoization causing re-renders | Comprehensive `createSelector` usage in `store/selectors/index.ts` — fix for #2537 verified |
| Vite missing code splitting | Manual chunking in vite.config.mts separates vendor/app. TrackList uses @tanstack/react-virtual for virtualization |
| Snapshot test overuse | Zero snapshot files found — tests use proper assertions |

### Pass 2

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| App.tsx missing ErrorBoundary around ComfortableApp | `index.tsx:41` wraps entire `<App />` in `<ErrorBoundary>` at the root level |
| useSimilarTracks loading state stuck when stale request completes | Latest request always calls `setLoading(false)` on completion; stale requests correctly skip state updates |
| useOptimisticUpdate stale closure on options callbacks | Standard React callback pattern — `execute` is recreated when `options` changes, new calls always use latest callbacks |
| ConnectionStatusIndicator timer memory leak | Timer callback is a no-op (empty function), any leaked timers self-fire after 2s. Minimal impact. |
| AlbumCharacterPane animation cleanup race condition | `mountedRef` pattern correctly prevents post-unmount state updates (standard React pattern) |
| StandardizedAPIClient `as` cast bypasses type safety | Covered by closed #2550 (accepted approach for this codebase) |
| EnhancementContext WebSocket handler uses `any` type | Sub-case of open #2598 (FE-12), not a separate finding |
| console.error in ErrorBoundary.tsx | Sub-case of open #2597 (FE-11), not a separate finding |

## Dimension Checklist Summary

### Dimension 1: Component Quality
- [x] Single responsibility — hooks handle logic, components handle rendering
- [ ] **Size guideline** — FE-14 (5 player components + AlbumCharacterPane exceed 300 lines)
- [x] Key usage — `key={`${track.id}-${index}`}` pattern correct
- [x] Memo usage — shallow React.memo replaces buggy custom comparator (#2540)
- [x] Error boundaries — ErrorBoundary wraps `<App />` at root (index.tsx:41)
- [x] Unmount guards — `mountedRef` pattern used in animation components (#2338)

### Dimension 2: Redux State Management
- [x] Normalized state — no duplication between playerSlice and queueSlice
- [x] Selector memoization — comprehensive `createSelector` usage (25+ memoized selectors)
- [x] Async error handling — thunks dispatch error states
- [x] Middleware — offline message queue with bounded size (100 max)
- [x] Serializable state — no functions or class instances in Redux

### Dimension 3: Hook Correctness
- [x] Dependency arrays — ref pattern prevents unnecessary deps (#2354, #2532)
- [x] useEffect cleanup — WebSocket, timers, AbortControllers all cleaned up
- [ ] **Race conditions** — FE-17 (useLibraryData loadMore closure stale guard)
- [x] WebSocket hooks — stable callback refs, reconnection, message queue
- [x] Fingerprint timeout — properly cleared in disconnect handler (#2536)
- [ ] **Pattern consistency** — FE-18 (usePlayNormal lacks ref indirection pattern)

### Dimension 4: TypeScript Type Safety
- [ ] **WebSocketContext `any`** — FE-12 (shadows typed discriminated union)
- [x] Type guards — 26 message type guards in types/websocket.ts
- [x] Domain types — camelCase interfaces with transformer layer
- [x] API response types — typed generics in standardizedAPIClient
- [ ] **Design system `as any`** — FE-19 (6 primitives bypass type safety on rest props)

### Dimension 5: Design System Adherence
- [x] Token usage — zero hardcoded hex/rgb colors in components
- [x] Import paths — 100% `@/` absolute imports
- [x] Spacing consistency — token-based spacing throughout
- [x] Glass surface system — 5 variants properly applied

### Dimension 6: API Client & Data Fetching
- [ ] **Error handling** — FE-16 (EnhancementContext swallows errors, no error state)
- [x] Request cancellation — AbortController per-request + unmount cleanup
- [x] Loading states — counter-based, handles concurrency
- [x] Transformer layer — per-entity snake→camel transformers with tests
- [x] Base URL — environment-based configuration (localhost for Electron)

### Dimension 7: Performance
- [ ] **Console logging** — FE-11 (178 statements, no production stripping)
- [x] List virtualization — @tanstack/react-virtual with overscan
- [x] Position updates — short-circuit when paused (#2543)
- [x] Streaming progress — debounced Redux dispatch (#2535)
- [x] Bundle splitting — vendor/app chunking in Vite config

### Dimension 8: Accessibility
- [ ] **Queue button aria-expanded** — FE-13 (toggle state not communicated)
- [x] ProgressBar — full slider implementation with ARIA, keyboard nav, live region
- [x] Player region — role="region", aria-label
- [x] Error alerts — role="alert", aria-live="assertive"
- [x] WCAG audit tool — comprehensive tool at `a11y/wcagAudit.ts` (622 lines)

### Dimension 9: Test Coverage
- [x] Player hooks — 9 test files covering core playback logic
- [x] Selectors — memoization and derivation tested
- [x] Integration tests — 7 test suites (player, streaming, enhancement, library, WS, error, a11y)
- [x] Component tests — ProgressBar, PlaybackControls, VolumeControl, TimeDisplay tested
- [x] No snapshot tests — proper assertion-based testing
- [ ] **Enhanced playback** — FE-15 (usePlayEnhanced and AudioPlaybackEngine untested)
