# Frontend Audit — 2026-03-04

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: 2 parallel exploration agents (Hooks/Redux/Store, Components/Services/A11y), followed by manual verification of all candidate findings against source code. All prior findings FE-24–FE-42 re-verified for deduplication. ~10 false positives eliminated.

## Executive Summary

This audit reveals **4 HIGH** and **5 MEDIUM** findings, mostly in hook correctness and performance. The most impactful finding is **FE-43** (HIGH): `useMasteringRecommendation` directly mutates a `useState` object, violating React's immutability contract. **FE-44** (HIGH): `useKeyboardShortcuts` recomputes its shortcuts array inline on every render, causing the `useEffect` to tear down and re-register all keyboard shortcuts on every parent re-render. **FE-47** (HIGH): The `QueuePanel` renders the entire queue without virtualization — with 100+ tracks, this creates hundreds of DOM nodes with event handlers. **FE-48** (HIGH): `usePlaybackProgress` subscribes to the entire `state.player` slice, causing re-renders on unrelated player state changes (volume, preset, streaming progress).

**Results**: 9 new confirmed findings (0 CRITICAL, 4 HIGH, 5 MEDIUM). Prior findings re-verified below.

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 4 | 2 | 6 |
| MEDIUM | 5 | 11 | 16 |
| LOW | 0 | 9 | 9 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 178 console.log statements, no production stripping | #2597 | **STILL OPEN** |
| FE-12: WebSocketContext propagates `any` instead of typed union | #2598 | **FIXED** — typed union imported from types/websocket.ts (commit `ae3e661d`) |
| FE-14: 5 player components exceed 300-line guideline | #2600 | **STILL OPEN** |
| FE-18: usePlayNormal passes handlers directly to subscribe | #2604 | **STILL OPEN** |
| FE-19: Design system primitives use `{...(props as any)}` | #2605 | **STILL OPEN** |
| FE-23: AudioPlaybackEngine and index.tsx use `window as any` | #2620 | **STILL OPEN** |
| FE-25: EnhancementContext shared isProcessing flag races | #2633 | **STILL OPEN** |
| FE-27: useSettingsDialog error state never rendered | #2635 | **STILL OPEN** |
| FE-28: queueSlice.setQueue([]) sets currentIndex to -1 | #2636 | **STILL OPEN** |
| FE-29: SettingsDialogHeader hardcodes color white | #2637 | **STILL OPEN** |
| FE-30: ScanStatusCard lacks aria-live region | #2638 | **STILL OPEN** |
| FE-31: Settings components use relative imports | #2639 | **FIXED** — all @/ absolute paths (commit `258fa3c3`) |
| FE-32: Six unused production dependencies | #2640 | **STILL OPEN** |
| FE-33: Nine duplicate Track interface definitions | #2662 | **FIXED** — orphaned re-exports removed (commit `3d0bbda8`) |
| FE-34: useSearchLogic fetches entire library per keystroke | — | **STILL OPEN** (no issue created yet) |
| FE-35: Queue context menus build incomplete track objects | — | **STILL OPEN** |
| FE-36: useQueue hook accepts `any` for all track actions | — | **STILL OPEN** |
| FE-37: useBatchOperations sequential raw fetch | — | **STILL OPEN** |
| FE-38: StandardizedAPIClient retries non-idempotent requests | — | **STILL OPEN** |
| FE-39: Custom modal dialogs lack role="dialog" and focus trapping | — | **STILL OPEN** |
| FE-40: usePlaybackState bypasses typed PlayerStateData with `as any` | — | **STILL OPEN** |
| FE-41: EditMetadataDialog hardcodes hex colors | #2651 | **STILL OPEN** |
| FE-42: SimilarityVisualization async effect lacks abort cleanup | #2645 | **STILL OPEN** |
| ArtworkResponse frontend type mismatch | #2627 | **STILL OPEN** |
| Hardcoded CSS colors in 4 source files | #2655 | **STILL OPEN** |
| Stale CRA proxy field in package.json | #2652 | **STILL OPEN** |
| Vite loader script embeds 6 console calls | #2656 | **STILL OPEN** |
| Missing regression tests for frontend fixes | #2669 | **STILL OPEN** |
| Vitest deprecated config options | #2673 | **STILL OPEN** |

## New Findings

---

### FE-43: `useMasteringRecommendation` directly mutates `useState` cache object
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useMasteringRecommendation.ts:41-57`
- **Status**: NEW — #2695
- **Description**: The hook creates a cache via `useState<MasteringRecommendationCache>({})` but only destructures the value — never the setter. The cache is then directly mutated via `cache[trackId] = rec` (line 56) and `delete cache[trackId]` (line 76). React state must never be mutated directly; this violates the immutability contract.
- **Evidence**:
  ```typescript
  // Line 41: Only destructures value, no setter
  const [cache] = useState<MasteringRecommendationCache>({});

  // Line 56: Direct mutation of React state!
  cache[trackId] = rec;

  // Line 76: Also mutates state directly
  delete cache[trackId];
  ```
- **Impact**: React cannot detect cache changes, so no re-renders are triggered by cache updates. The cache check (`if (cache[trackId])`) works by accident because the object reference is stable. Under React StrictMode double-renders or concurrent features, this could produce inconsistent state. The cache is effectively a ref masquerading as state.
- **Suggested Fix**: Replace `useState` with `useRef` (since the cache doesn't drive renders), or use `useState` properly with a setter function for immutable updates.

---

### FE-44: `useKeyboardShortcuts` recomputes shortcuts array inline, causing effect churn
- **Severity**: HIGH
- **Dimension**: Hook Correctness / Performance
- **Location**: `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:187-210`
- **Status**: NEW — #2696
- **Description**: `shortcutsToRegister` is computed inline on every render (via `configToServiceShortcuts()` which returns a new array). This array is used in the `useEffect` dependency array, causing the effect to clear and re-register ALL keyboard shortcuts on every render of any parent component.
- **Evidence**:
  ```typescript
  // Lines 187-189: New array created every render
  const shortcutsToRegister = Array.isArray(configOrShortcuts)
    ? configOrShortcuts
    : configToServiceShortcuts(configOrShortcuts || {});

  // Line 210: Effect depends on the non-memoized array
  useEffect(() => {
    keyboardShortcuts.clear();
    shortcutsToRegister.forEach((shortcut) => { /* register */ });
    keyboardShortcuts.startListening();
    return () => { keyboardShortcuts.stopListening(); keyboardShortcuts.clear(); };
  }, [shortcutsToRegister]);
  ```
- **Impact**: Keyboard shortcuts are torn down and re-registered on every render. During re-registration, shortcuts are briefly unresponsive. This also causes `stopListening()`/`startListening()` to fire repeatedly, potentially dropping key events.
- **Suggested Fix**: Wrap `shortcutsToRegister` in `useMemo` with the config object as dependency.

---

### FE-45: `usePlayerAPI.playTrack` depends on entire `playerState`, recreated on every WebSocket update
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness / Performance
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts:248-257`
- **Status**: NEW — #2697
- **Description**: The `playTrack` callback depends on `playerState` in its dependency array. Since `playerState` changes on every WebSocket `player_state` broadcast (every second during playback), the callback is recreated every second. Any consumer that depends on `playTrack` (in a `useCallback` or `useEffect`) also re-executes every second.
- **Evidence**:
  ```typescript
  const playTrack = useCallback(async (track: PlayerTrack) => {
    if (playerState.currentTrack?.id === track.id && playerState.isPlaying) {
      return;
    }
    await setQueue([track], 0);
  }, [setQueue, playerState]); // <-- playerState changes every second
  ```
- **Impact**: Downstream hooks and components that depend on `playTrack` identity (e.g., in TrackRow onClick handlers) re-render on every WebSocket position update, causing unnecessary work across the entire track list.
- **Suggested Fix**: Use a ref for the guard check (`currentTrackIdRef`, `isPlayingRef`) and remove `playerState` from the dependency array.

---

### FE-46: `usePlayNormal` subscribes to WebSocket inside `playNormal()` instead of on mount
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:406-476`
- **Status**: Existing: #2604
- **Description**: Unlike `usePlayEnhanced` (which subscribes on mount via a `useEffect` with stable refs), `usePlayNormal` subscribes inside the `playNormal()` callback. The handler functions are listed as dependencies of `playNormal`, causing the callback to be recreated whenever any handler changes.
- **Impact**: Race condition: if the backend sends `audio_stream_start` before the subscription completes, the message is lost. Already tracked as #2604.

---

### FE-47: `QueuePanel` renders full queue without virtualization
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:224-245`
- **Status**: NEW — #2698
- **Description**: The queue renders every track as a DOM node via `.map()`. Each `QueueTrackItem` includes drag-and-drop event handlers, hover state, focus tracking, and context menu bindings. The main library `TrackList` correctly uses `@tanstack/react-virtual`, but `QueuePanel` does not.
- **Evidence**:
  ```tsx
  <ul style={styles.queueList}>
    {queue.map((track, index) => (
      <QueueTrackItem
        key={`${track.id}-${index}`}
        track={track}
        index={index}
        // ... 10+ props including drag handlers
      />
    ))}
  </ul>
  ```
- **Impact**: With 100+ tracks (common for album-based queuing), this creates hundreds of DOM nodes with event handlers, causing slow rendering, high memory usage, and janky scrolling. Each Player re-render (which happens every second during playback, see FE-45 context) forces React to diff the entire queue list.
- **Suggested Fix**: Add `@tanstack/react-virtual` (already a project dependency) to virtualize the queue list.

---

### FE-48: `usePlaybackProgress` subscribes to entire `state.player` slice
- **Severity**: HIGH
- **Dimension**: Performance / Redux State
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:388-391`
- **Status**: NEW — #2699
- **Description**: `usePlaybackProgress()` calls `usePlayerState()` which returns the entire `state.player` object. This causes re-renders on ANY player state change (volume, preset, mute, streaming progress, error), not just `currentTime`/`duration` changes.
- **Evidence**:
  ```typescript
  // Line 388-391
  export const usePlaybackProgress = () => {
    const { currentTime, duration } = usePlayerState();
    return duration > 0 ? currentTime / duration : 0;
  };

  // usePlayerState returns entire slice:
  export const usePlayerState = () => {
    return useSelector((state: RootState) => state.player);
  };
  ```
- **Impact**: Components using `usePlaybackProgress()` (e.g., progress bars) re-render on volume changes, preset changes, streaming updates, and any other `state.player` mutations — far more often than necessary. The progress bar only needs `currentTime` and `duration`.
- **Suggested Fix**: Use granular selectors: `useSelector(selectCurrentTime)` and `useSelector(selectDuration)`.

---

### FE-49: `selectRemainingTime` and `selectTotalQueueTime` are non-memoized selectors that compute on every call
- **Severity**: MEDIUM
- **Dimension**: Redux State / Performance
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:262-273`
- **Status**: NEW — #2700
- **Description**: These selectors compute derived values (`.slice().reduce()`) on every call without memoization. Memoized versions exist in `store/selectors/index.ts`, but these non-memoized versions in the slice file are exported and may be imported by consumers directly.
- **Evidence**:
  ```typescript
  // queueSlice.ts:262-268 — recomputes on every call
  export const selectRemainingTime = (state: { queue: QueueState }) => {
    return state.queue.tracks
      .slice(state.currentIndex + 1)
      .reduce((sum, track) => sum + track.duration, 0);
  };
  ```
- **Impact**: If consumed via `useSelector`, this runs on every Redux state change (not just queue changes), creating a new number value each time. The `.slice()` creates a new array on every call.
- **Suggested Fix**: Remove these non-memoized exports from the slice file. Ensure consumers import from `store/selectors/index.ts` which has the `createSelector` versions.

---

### FE-50: `useVisualizationOptimization` uses empty dependency array, ignoring config changes
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useVisualizationOptimization.ts:66`
- **Status**: NEW — #2701
- **Description**: The `useEffect` that initializes the `PerformanceOptimizer` has an empty dependency array `[]`, but uses `autoAdjustQuality` and `optimizerConfig` from the closure. If these props change after mount, the optimizer is not re-initialized with the new config.
- **Evidence**:
  ```typescript
  useEffect(() => {
    optimizerRef.current = new PerformanceOptimizer({
      adaptiveQuality: autoAdjustQuality,
      ...optimizerConfig
    });
    return () => { optimizerRef.current?.cleanup(); };
  }, []); // <-- missing autoAdjustQuality, optimizerConfig
  ```
- **Impact**: If a parent component toggles `autoAdjustQuality` or changes `optimizerConfig`, the optimizer continues running with the original config. The visualization quality settings become "stuck" at mount-time values.
- **Suggested Fix**: Add `autoAdjustQuality` and a stable reference to `optimizerConfig` to the dependency array.

---

### FE-51: `useVisualizationOptimization` returns non-null asserted refs that may be undefined on first render
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/shared/useVisualizationOptimization.ts:141,149`
- **Status**: NEW — #2702
- **Description**: The hook returns `optimizerRef.current!` and `monitorRef.current!` using the non-null assertion operator. On the first render, before the `useEffect` runs, these are `undefined`. Any consumer that synchronously accesses `.optimizer.someMethod()` during initial render will get a runtime error.
- **Evidence**:
  ```typescript
  return {
    optimizer: optimizerRef.current!,  // undefined before first effect
    monitor: monitorRef.current!       // undefined before first effect
  };
  ```
- **Impact**: Runtime `TypeError: Cannot read properties of undefined` if a consumer calls methods on these values before the effect initializes them. Low probability since most consumers use them in effects/handlers (not render), but the type contract is misleading.
- **Suggested Fix**: Return `optimizerRef.current ?? null` and type the return as `PerformanceOptimizer | null`, forcing consumers to null-check.
