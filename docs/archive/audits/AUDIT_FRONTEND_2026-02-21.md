# Frontend Audit — 2026-02-21

**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Newest existing issue at audit start**: #2531
**Report**: 28 findings (FE-01 – FE-28), all NEW unless marked otherwise
**Issues created**: #2532 – #2558 (26 new issues; FE-10 noted as regression on #2139)

---

## Severity Summary

| Severity | Count |
|----------|-------|
| HIGH | 8 |
| MEDIUM | 13 |
| LOW | 7 |

---

## HIGH Severity

### FE-01: usePlayEnhanced Re-subscription Loses Messages Mid-Stream on Reconnect
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:678-712`
- **Status**: NEW
- **Description**: The mount effect that subscribes to WebSocket streaming messages lists `handleStreamStart`, `handleChunk`, `handleStreamEnd`, `handleStreamError`, and `handleFingerprintProgress` as dependencies. Each of these is a `useCallback` with its own deps. If any dependency changes (e.g., `wsContext` reference changes on reconnect), the effect cleanup runs (unsubscribing all handlers) and setup re-runs (resubscribing). Any `audio_stream_start` or `audio_chunk` message that arrives in the gap between unsubscribe and resubscribe is permanently lost, causing playback to stall or never start.
- **Evidence**:
  ```typescript
  }, [wsContext, handleStreamStart, handleChunk, handleStreamEnd, handleStreamError, handleFingerprintProgress]);
  // On reconnect, wsContext changes → effect re-runs → gap exists during cleanup → setup
  ```
- **Impact**: On WebSocket reconnect mid-stream, an audio_stream_start message in the gap results in an uninitialised PCMStreamBuffer — subsequent audio_chunk messages queue indefinitely and playback never starts.
- **Suggested Fix**: Use stable ref-based subscriptions (as done in `useWebSocketSubscription.ts`) to avoid resubscribing on every callback recreation. Store callbacks in refs and subscribe once on mount.

---

### FE-02: Streaming State Fragmented Between Redux and Hook Refs
- **Severity**: HIGH
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:176-178,304-309` / `auralis-web/frontend/src/store/slices/playerSlice.ts:56-59`
- **Status**: NEW
- **Description**: Streaming state is split across two systems: `pcmBufferRef`, `playbackEngineRef`, `audioContextRef`, and `streamingMetadataRef` are hook refs; Redux stores `streaming.enhanced.{state, progress, trackId, totalChunks}`. If the hook unmounts and remounts (navigation, reconnect), refs reset to null while Redux retains stale `state: 'streaming'` and non-zero `progress`. The UI then shows a phantom progress bar for a stream that no longer exists, and the new stream's events may be dropped while the stale Redux state misleads consumers.
- **Evidence**:
  ```typescript
  // Refs reset on unmount but Redux is NOT reset:
  const pcmBufferRef = useRef<PCMStreamBuffer | null>(null);       // → null on remount
  const streamingMetadataRef = useRef<{...} | null>(null);         // → null on remount
  // Redux persists:
  dispatch(startStreaming({ streamType: 'enhanced', trackId, totalChunks }));  // Not cleared on remount
  ```
- **Impact**: Stale Redux streaming state causes phantom progress UI, incorrect `isStreaming` selectors, and potential double-processing of stream events on remount.
- **Suggested Fix**: Dispatch `resetStreaming('enhanced')` in the mount effect's cleanup, or add a `useEffect` that dispatches reset when the hook mounts with `pcmBufferRef.current === null`.

---

### FE-03: Track Data Duplicated Across playerSlice and queueSlice
- **Severity**: HIGH
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:19-26` / `auralis-web/frontend/src/store/slices/queueSlice.ts`
- **Status**: NEW
- **Description**: `playerSlice.currentTrack: Track | null` and `queueSlice.tracks: Track[]` both store full Track objects. When a track is loaded, two separate dispatches must update both slices. If one dispatch is dropped, missed, or ordered incorrectly, `currentTrack` and `queue.tracks[currentIndex]` diverge, causing the player UI to show different track metadata than the queue highlights.
- **Evidence**:
  ```typescript
  // playerSlice.ts — denormalized copy
  currentTrack: Track | null;
  // queueSlice.ts — array of the same Track objects
  tracks: Track[];
  // Two separate dispatches required to stay consistent
  ```
- **Impact**: Race-prone updates (rapid skip/back) can leave `currentTrack` and `queue.tracks[currentIndex]` out of sync — player header shows Track A while queue highlight shows Track B.
- **Suggested Fix**: Store only `currentIndex` in `playerSlice`. Derive `currentTrack` via a selector: `state.queue.tracks[state.player.currentIndex]`. Eliminates the duplication entirely.

---

### FE-04: updateStreamingProgress Dispatched Per Chunk — High Redux Churn
- **Severity**: HIGH
- **Dimension**: Redux State Management
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:415-423` / `auralis-web/frontend/src/store/slices/playerSlice.ts:318-340`
- **Status**: NEW
- **Description**: `updateStreamingProgress` is dispatched for every received audio chunk. For typical tracks (30 chunks at 30s each, or more for gapless), this generates many dispatches in quick succession. Each dispatch runs through Redux middleware, records a DevTools action, and triggers `useSelector` comparisons in all subscribed components. The `updatePlaybackState` reducer also uses `Object.assign` for nested updates, which means every chunk update causes a new object reference for `state.streaming.enhanced`, invalidating all derived selectors.
- **Evidence**:
  ```typescript
  // Called on EVERY chunk received:
  dispatch(updateStreamingProgress({
    streamType: 'enhanced',
    processedChunks: streamingMetadataRef.current.processedChunks,
    bufferedSamples,
    progress: Math.min(progress, 100),
  }));
  ```
- **Impact**: Redux DevTools becomes noisy, selector comparisons run excessively, performance degrades on long tracks. Components displaying `selectStreamingProgress` re-render on every chunk.
- **Suggested Fix**: Track progress in a local `useRef` and only dispatch to Redux at meaningful thresholds (e.g., every 10% progress or on stream completion). Use a debounced dispatch for UI updates.

---

### FE-05: usePlayEnhanced Disconnection Handler Does Not Reset pendingChunksRef
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:723-745`
- **Status**: NEW
- **Description**: When `wsContext.isConnected` transitions to `false`, the disconnection effect clears `pcmBufferRef`, `playbackEngineRef`, `streamingMetadataRef`, and `pendingChunksRef`. However, if reconnection immediately follows (fast reconnect), and a new `audio_stream_start` arrives, `handleStreamStart` sets `pcmBufferRef.current` (line 263) BEFORE processing `pendingChunksRef` (line 325). During the window between these two lines within the synchronous execution of `handleStreamStart`, any reference to `pendingChunksRef` reflects the correct cleared state. The real danger is `fingerprintTimeoutRef` — it is cleared in `cleanupStreaming()` but NOT in the disconnection effect, so fingerprint status messages can persist as "Analyzing…" long after the stream is torn down.
- **Evidence**:
  ```typescript
  // Disconnection effect (lines 723-745) clears pcmBufferRef but NOT fingerprintTimeoutRef:
  if (!wsContext.isConnected && playbackEngineRef.current) {
    playbackEngineRef.current.stopPlayback();
    pcmBufferRef.current = null;
    pendingChunksRef.current = [];   // ← cleared
    // fingerprintTimeoutRef NOT cleared → stale "Analyzing..." status persists
  }
  ```
- **Impact**: After disconnect, the fingerprint status spinner remains visible indefinitely. User sees "Analyzing fingerprint…" for orphaned streams.
- **Suggested Fix**: Clear `fingerprintTimeoutRef` in the disconnection effect: `clearTimeout(fingerprintTimeoutRef.current); fingerprintTimeoutRef.current = null;`.

---

### FE-06: useReduxState Hook Returns New Object Reference Every Call
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:42-90`
- **Status**: NEW
- **Description**: `usePlayer()` returns a new object literal on every render, containing 15+ `useCallback` hooks where some depend on `state.isPlaying` and other frequently-changing state. Any parent component that passes this return value as a prop or provides it through context will re-render all consumers on every player state change, even when the consuming component only uses one field.
- **Evidence**:
  ```typescript
  export const usePlayer = () => {
    const state = useSelector((state: RootState) => state.player);
    return {
      // Returned as a NEW object literal every render:
      play: useCallback(() => dispatch(playerActions.setIsPlaying(true)), [dispatch]),
      togglePlay: useCallback(
        () => dispatch(playerActions.setIsPlaying(!state.isPlaying)),
        [dispatch, state.isPlaying]  // Changes on every play/pause
      ),
      // ... 13 more callbacks
    };
  };
  ```
- **Impact**: Every component using `usePlayer()` re-renders when any player state changes (position, volume, queue index), even when only `isPlaying` is used. With WebSocket position updates at 10Hz, this can cause 10 re-renders/sec across all consumers.
- **Suggested Fix**: Split into granular hooks (`usePlayerControls()`, `usePlayerState()`) or use `useMemo` to stabilise the return object. Selector hooks should be subscribed individually per field.

---

### FE-07: ProgressBar Missing ARIA Live Updates During Drag and Touch
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/ProgressBar.tsx:283-329`
- **Status**: NEW (relates to Existing: #2136 but is a specific unaddressed case)
- **Description**: The ProgressBar has `role="slider"` with correct `aria-valuenow`, but `aria-valuenow` is only updated on mouse/touch RELEASE, not during drag. Screen reader users dragging the slider receive no continuous position feedback. Touch interactions (`onTouchStart`, `onTouchMove`) have no corresponding ARIA announcements. There is no `aria-live` region announcing drag start/end state.
- **Evidence**:
  ```typescript
  <div
    role="slider"
    aria-valuenow={Math.round(currentTime)}  // Only on release, not during drag
    onTouchStart={handleTouchStart}           // No aria-live announcement
    onTouchMove={handleTouchMove}             // No aria-label update during move
  >
  ```
- **Impact**: Screen reader users navigating with touch cannot determine their position during seek. WCAG 2.1 SC 4.1.3 (Status Messages) violation.
- **Suggested Fix**: Update `aria-valuenow` during drag (throttled), add an `aria-live="polite"` region that announces position changes during seek, and emit ARIA status on drag start/end.

---

### FE-08: Prop Drilling in TrackRow — 14 Callback Props
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:30-103`
- **Status**: NEW
- **Description**: `TrackRowProps` defines 14 separate callback props (`onPlay`, `onPause`, `onDoubleClick`, `onEditMetadata`, `onFindSimilar`, `onToggleFavorite`, `onShowAlbum`, `onShowArtist`, `onShowInfo`, `onDelete`, plus 3 state flags). These are all threaded through from parent list components through the TrackRow into `useTrackContextMenu` and `useTrackRowHandlers`, coupling every ancestor to TrackRow's internal detail requirements.
- **Evidence**:
  ```typescript
  interface TrackRowProps {
    track: Track; index: number; isPlaying?: boolean; isCurrent?: boolean; isAnyPlaying?: boolean;
    onPlay: (trackId: number) => void; onPause?: () => void; onDoubleClick?: (trackId: number) => void;
    onEditMetadata?: (trackId: number) => void; onFindSimilar?: (trackId: number) => void;
    onToggleFavorite?: (trackId: number) => void; onShowAlbum?: (albumId: number) => void;
    onShowArtist?: (artistName: string) => void; onShowInfo?: (trackId: number) => void;
    onDelete?: (trackId: number) => void;
  }
  ```
- **Impact**: Any refactoring of track actions requires updating every ancestor in the component tree. Makes parent components brittle to TrackRow implementation changes. Increases re-render surface (14 callback identity comparisons per row).
- **Suggested Fix**: Replace callback drilling with a `TrackActionsContext` (already partially established with `ContextMenu`). TrackRow reads `dispatch` directly for Redux actions; contextual callbacks (navigate to album/artist) go through context.

---

## MEDIUM Severity

### FE-09: TrackRow React.memo Custom Comparator Ignores Callback Props
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:185-197`
- **Status**: NEW
- **Description**: The custom memo comparator checks only `track.id`, `isPlaying`, `isCurrent`, `isAnyPlaying`, and `index`. It ignores all 9 callback props. If parent components recreate these callbacks without `useCallback`, the component will NOT re-render (memo skips it), leaving handlers silently stale.
- **Evidence**:
  ```typescript
  export const TrackRow = React.memo<TrackRowProps>(
    TrackRowComponent,
    (prev, next) => (
      prev.track.id === next.track.id && prev.isPlaying === next.isPlaying &&
      prev.isCurrent === next.isCurrent && prev.isAnyPlaying === next.isAnyPlaying &&
      prev.index === next.index
      // 9 callback props NOT checked
    )
  );
  ```
- **Impact**: Stale closure bugs where clicks use outdated handler logic — e.g., `onToggleFavorite` captures old favourite state and toggles incorrectly.
- **Suggested Fix**: Either (a) remove the custom comparator and rely on default shallow comparison (requiring `useCallback` in parents), or (b) add callback comparisons using `Object.is`.

---

### FE-10: Player.tsx Exceeds 300-Line Guideline at 343 Lines
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:1-405`
- **Status**: Regression of #2139
- **Description**: Player.tsx has grown to 343 lines (305-line rendered JSX + hooks). It handles WebSocket streaming setup (79-96), queue navigation (119-176), play/pause toggling (178-204), volume control (206-219), auto-advance logic (221-246), and UI rendering (260-403). CLAUDE.md mandates < 300 lines per module with single responsibility.
- **Evidence**: File is 405 lines total; component definition spans lines 63-405 (343 lines).
- **Impact**: High cognitive complexity, difficult to test individual responsibilities, larger diff surface for bugs.
- **Suggested Fix**: Extract `useAutoAdvance()` hook for the auto-advance logic (lines 221-246). Consider splitting the streaming setup section into `usePlayerStreaming` or similar.

---

### FE-11: QueuePanel / ErrorBanner Conditional Mount Causes DOM Instability
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:361-368,395-402`
- **Status**: NEW
- **Description**: QueuePanel and the error banner are conditionally rendered (`&&` pattern), mounting and unmounting on every toggle. This discards internal state (scroll position, focus), loses event listener registrations inside QueuePanel, and prevents CSS transition animations. For the error banner, repeated mount/unmount on re-renders creates flicker.
- **Evidence**:
  ```typescript
  {queuePanelOpen && (
    <Box sx={styles.queuePanelWrapper}>
      <QueuePanel collapsed={false} ... />  {/* Unmounts on close — loses scroll position */}
    </Box>
  )}
  ```
- **Impact**: Closing and reopening queue always resets scroll to top. Any focused element inside QueuePanel loses focus, breaking keyboard navigation. CSS animations cannot play on unmount.
- **Suggested Fix**: Keep elements mounted; toggle visibility with CSS `display: none` or `visibility: hidden`. Pass `isVisible` prop to QueuePanel for internal lazy rendering.

---

### FE-12: usePlaybackState Subscribes to position_changed — 10 Re-renders/sec During Playback
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:62-72`
- **Status**: NEW
- **Description**: `usePlaybackState` subscribes to `position_changed` WebSocket messages (among 7 others) and calls `setState` on every message. With the backend sending position at 10Hz, every component using `usePlaybackState` re-renders 10 times per second during playback, regardless of which field it consumes.
- **Evidence**:
  ```typescript
  useWebSocketSubscription(
    ['player_state', 'playback_started', ..., 'position_changed', 'volume_changed'],
    (message) => { setState(prevState => { switch (message.type) { ... } }); }
  );
  // position_changed at 10Hz → 10 setState calls/sec
  ```
- **Impact**: With multiple components consuming `usePlaybackState`, this causes cascading re-renders. On slow devices, this creates perceptible jank in the queue list.
- **Suggested Fix**: Separate `position_changed` into its own hook (`usePlaybackPosition`) returning only a ref (not state) for rendering, and use `requestAnimationFrame` to throttle DOM updates.

---

### FE-13: useWebSocketSubscription Missing Cleanup When Manager Reference Changes
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:128-129`
- **Status**: NEW
- **Description**: The subscription effect depends on `messageTypes.join('\x00')` (a string) but not on the underlying WebSocket manager object. On reconnect, if the manager reference changes without `messageTypes` changing, the effect does not re-run and the subscription is not re-established on the new manager. The workaround at lines 98-100 unsubscribes the old callback when the manager-ready event fires, but if the new manager emits messages before the ready event, those messages are missed.
- **Evidence**:
  ```typescript
  }, [messageTypes.join('\x00')]); // Only string key — manager changes not detected
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ```
- **Impact**: After WebSocket reconnect, subscription to messages may silently fail for the window between manager change and ready event. Playback state hooks may miss `playback_started` or `track_loaded` messages.
- **Suggested Fix**: Include a stable manager identity (e.g., `wsManager?.id`) in the dependency array, or respond to manager change events in the existing cleanup/setup pattern.

---

### FE-14: 100ms setInterval in usePlayerStreaming Causes Render Churn When Paused
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStreaming.ts:216-246`
- **Status**: NEW
- **Description**: A `setInterval` at 100ms (10Hz) polls `audioElement.currentTime` and calls `setState` even when playback is paused. The update is guarded by shallow equality, but React still invokes the comparator 10 times per second. For the duration of the app's lifecycle (including background tabs), this interval never sleeps.
- **Evidence**:
  ```typescript
  const interval = setInterval(() => {
    const time = audioElement.currentTime;
    // ... reads 6 properties from audio element
    setState((prev) => {
      if (prev.currentTime !== time || ...) return { ...prev, currentTime: time };
      return prev;  // setState still called 10x/sec even when unchanged
    });
  }, updateInterval);  // 100ms
  ```
- **Impact**: 600 setState invocations per minute even when paused. Prevents CPU idle on battery devices.
- **Suggested Fix**: Replace with `requestAnimationFrame` loop that suspends when `audioElement.paused`. Or use `audioElement.ontimeupdate` event (fires only during playback) supplemented with a low-frequency fallback.

---

### FE-15: Queue remainingTime and totalTime Recomputed O(n) on Every Render
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:120-123`
- **Status**: NEW
- **Description**: `useQueueState()` computes `remainingTime` (slice + reduce) and `totalTime` (reduce) synchronously on every call, without memoisation. With `usePlayer()` already causing high re-render rates (see FE-06), a queue of 500+ tracks performs two O(n) array operations per re-render cycle.
- **Evidence**:
  ```typescript
  remainingTime: state.tracks
    .slice(state.currentIndex + 1)  // new array allocation
    .reduce((sum, track) => sum + track.duration, 0),  // O(n)
  totalTime: state.tracks.reduce((sum, track) => sum + track.duration, 0),  // O(n)
  ```
- **Impact**: At 10Hz re-renders with a 1000-track queue, ~20,000 array operations per second. Measurable CPU overhead on lower-end devices.
- **Suggested Fix**: Move these computations into `createSelector` memoised selectors so they only recompute when `tracks` or `currentIndex` changes.

---

### FE-16: QueueSearchPanel Missing Modal Role, Focus Trap, and Escape Key
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueueSearchPanel.tsx`
- **Status**: NEW (specific to this component; relates to #2136)
- **Description**: The panel renders as a modal overlay using a plain `<div onClick={onClose}>` with no `role="dialog"`, no `aria-modal="true"`, no focus trap implementation, and no keyboard escape handler documented. Tab focus escapes the panel bounds; screen readers are not aware they're inside a modal context.
- **Evidence**:
  ```typescript
  <div style={styles.overlay} onClick={onClose}>
    <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
      {/* No role="dialog", no aria-modal, no focus management */}
  ```
- **Impact**: Keyboard-only users cannot dismiss panel with Escape. Tab order is unbounded. WCAG 2.1 SC 2.1.2 (No Keyboard Trap) and 4.1.2 (Name, Role, Value) violations.
- **Suggested Fix**: Add `role="dialog"`, `aria-modal="true"`, `aria-label`, an `onKeyDown` handler for Escape, and implement focus trapping with `focus-trap-react` or a custom hook.

---

### FE-17: GlobalSearch Missing ARIA Live Region for Result Count
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Search/GlobalSearch.tsx:36-72`
- **Status**: NEW
- **Description**: The search component populates results dynamically but provides no `aria-live` region to announce result count to screen readers. Users who type a query have no notification that results have loaded, how many were found, or when the search is empty.
- **Evidence**:
  ```typescript
  <ResultsContainerComponent
    visible={showResults}
    results={results}
    loading={loading}
    // No aria-live, no aria-atomic, no result count announcement
  />
  ```
- **Impact**: Screen reader users don't know when results appear or how many exist. WCAG 2.1 SC 4.1.3 (Status Messages) violation.
- **Suggested Fix**: Add a visually-hidden `<span aria-live="polite" aria-atomic="true">` that announces `"${results.length} results for ${query}"` when results change.

---

### FE-18: WebSocket Message Type Guards Cover Only 10 of 26 Message Types
- **Severity**: MEDIUM
- **Dimension**: TypeScript Type Safety
- **Location**: `auralis-web/frontend/src/types/websocket.ts:422-464`
- **Status**: NEW
- **Description**: The WebSocket types file defines 26 message types in the `AnyWebSocketMessage` discriminated union, but only 10 have corresponding type guard functions. Missing guards for: `TrackLoadedMessage`, `TrackChangedMessage`, `PositionChangedMessage`, `VolumeChangedMessage`, `QueueUpdatedMessage`, `QueueChangedMessage`, `LibraryUpdatedMessage`, `PlaylistCreatedMessage`, `PlaylistUpdatedMessage`, `PlaylistDeletedMessage`, and others. Consumers handling these message types must use unsafe casts or string comparisons.
- **Evidence**:
  ```typescript
  // Only 10 guards defined; 16+ types use fallback pattern:
  if (message.type === 'position_changed') {
    const { position } = (message as PositionChangedMessage).data;  // ← Unsafe cast
  }
  ```
- **Impact**: Type safety gaps allow mismatches between actual message shape and assumed shape to be caught only at runtime. Backend schema changes go undetected at compile time.
- **Suggested Fix**: Add type guards for all remaining message types, or generate them from the discriminated union using a utility: `function isMessage<T extends AnyWebSocketMessage>(type: T['type']): (msg: AnyWebSocketMessage) => msg is T`.

---

### FE-19: processingService.handleWebSocketMessage Receives Untyped `any`
- **Severity**: MEDIUM
- **Dimension**: TypeScript Type Safety
- **Location**: `auralis-web/frontend/src/services/processingService.ts:152`
- **Status**: NEW
- **Description**: The WebSocket message handler in `processingService` is typed as `any`, bypassing the comprehensive `AnyWebSocketMessage` discriminated union defined in `types/websocket.ts`. It accesses `message.data.job_id`, `message.data.progress` without validation.
- **Evidence**:
  ```typescript
  private handleWebSocketMessage(message: any) {   // ← any, not AnyWebSocketMessage
    if (message.type === 'job_progress') {
      const { job_id, progress, message: progressMessage } = message.data;  // Unsafe
  ```
- **Impact**: If the backend changes the `job_progress` message shape, this code silently breaks with a runtime error rather than a compile-time failure.
- **Suggested Fix**: Type the parameter as `AnyWebSocketMessage`, use the appropriate type guard, and narrow to `JobProgressMessage` before destructuring.

---

### FE-20: API Responses Accepted Without Runtime Shape Validation
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:280-285`
- **Status**: NEW
- **Description**: API responses are cast directly to the expected type with no runtime validation: `return data as SuccessResponse<T>`. The response JSON is trusted to match the TypeScript interface. If the backend returns unexpected fields, missing required fields, or wrong types, the error surfaces downstream (undefined access, NaN in displays) rather than at the API boundary.
- **Evidence**:
  ```typescript
  const data = await response.json();
  return data as SuccessResponse<T>;   // Cast, no runtime validation
  ```
- **Impact**: Schema drift between backend and frontend goes undetected until user-visible symptoms appear. Debug sessions are longer because the error manifests far from the root cause.
- **Suggested Fix**: Add a lightweight runtime check using Zod (already in devDependencies?) or a minimal schema assertion for critical responses (track, album, queue).

---

### FE-21: Hardcoded `localhost:8765` as Production WebSocket URL
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/config/api.ts:11-14`
- **Status**: NEW
- **Description**: The WebSocket URL is hardcoded to `ws://localhost:8765` with no environment variable override. The HTTP API URL correctly uses an empty string in dev (proxy) but falls back to `http://localhost:8765` in production. Both fail in any deployment outside localhost.
- **Evidence**:
  ```typescript
  export const API_BASE_URL = import.meta.env.DEV ? '' : 'http://localhost:8765';
  export const WS_BASE_URL = 'ws://localhost:8765';  // Always localhost — no env override
  ```
- **Impact**: Auralis cannot be deployed to any server other than localhost without modifying source code. Breaks Docker deployments, remote access, and production builds.
- **Suggested Fix**:
  ```typescript
  export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8765';
  export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? '' : 'http://localhost:8765');
  ```

---

### FE-22: usePlaybackState position_changed Causes Broad Re-subscription on Reconnect
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:62-72`
- **Status**: NEW
- **Description**: `usePlaybackState` uses a single `useWebSocketSubscription` call for 8 different message types including both low-frequency state events and high-frequency `position_changed`. This single handler cannot be granularly unsubscribed — any reconnect causes all 8 subscriptions to re-establish simultaneously, creating a brief window where all player state events may be missed.
- **Evidence**: The combined subscription list mixes event types with very different frequencies:
  ```typescript
  ['player_state', 'playback_started', 'playback_paused', 'playback_stopped',
   'track_loaded', 'track_changed', 'position_changed', 'volume_changed']
  ```
- **Impact**: On reconnect, a burst of missed state events (playback_stopped, track_changed) can leave the frontend UI out of sync with the backend until the next event of each type arrives.
- **Suggested Fix**: Separate `position_changed` into a dedicated subscription. Consider grouping state events differently so critical state events (track_loaded, playback_stopped) can be re-established more reliably.

---

---

## LOW Severity

### FE-23: Hardcoded Gradient Colors in MediaCardArtwork.tsx
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx:38-43`
- **Status**: NEW (specific to this file; relates to Existing: #2135)
- **Description**: Five gradient definitions use hardcoded hex values not from `tokens.colors`. The design system tokens (`tokens.colors.accent.primary`, `tokens.colors.accent.secondary`, `tokens.colors.semantic.success`) exist at similar hue values, but the gradients bypass the token system entirely, making them immune to theme changes.
- **Evidence**:
  ```typescript
  const colors = [
    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',  // Not from tokens
    'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    // ...
  ];
  ```
- **Impact**: Placeholder artwork colors will not adapt if the design system colour palette changes. Minor visual inconsistency with the rest of the UI.
- **Suggested Fix**: Replace with gradients built from `tokens.colors.accent.*` and `tokens.colors.semantic.*`.

---

### FE-24: Generic `any` Defaults in ApiResponse and useStandardizedAPI
- **Severity**: LOW
- **Dimension**: TypeScript Type Safety
- **Location**: `auralis-web/frontend/src/types/api.ts:14,20` / `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:60`
- **Status**: NEW
- **Description**: `ApiResponse<T = any>`, `ApiListResponse<T = any>`, and `useStandardizedAPI<T = any>` all default to `any` when the caller omits the type parameter. Callers that forget the generic get silently untyped data.
- **Evidence**:
  ```typescript
  export interface ApiResponse<T = any> { data: T; ... }         // Should be T = unknown
  export function useStandardizedAPI<T = any>(...): APIRequestState<T>  // Should require T
  ```
- **Impact**: Silently allows untyped API usage to compile. IDE autocomplete is unavailable for `data` fields when callers omit the type argument.
- **Suggested Fix**: Change defaults to `unknown` and add ESLint rule `@typescript-eslint/no-explicit-any` to catch future any usages.

---

### FE-25: Non-Null Assertion Operator Used in Production Components
- **Severity**: LOW
- **Dimension**: TypeScript Type Safety
- **Location**: `auralis-web/frontend/src/components/enhancement-pane/sections/MasteringRecommendation/MasteringRecommendation.tsx:123`
- **Status**: NEW
- **Description**: `recommendation.weighted_profiles!.map(...)` uses a non-null assertion. While a preceding guard makes this safe in practice, the `!` operator is a promise to the TypeScript compiler that could be violated if the guard logic changes.
- **Evidence**:
  ```typescript
  {recommendation.weighted_profiles!.map((profile, idx) => (
  ```
- **Impact**: Low immediate risk, but establishes a pattern of suppressing rather than fixing type errors.
- **Suggested Fix**: Replace with optional chaining: `recommendation.weighted_profiles?.map(...)`.

---

### FE-26: Relative Imports in Enhancement Pane Components
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/enhancement-pane/sections/AudioCharacteristics/AudioCharacteristics.tsx:14` and `Expanded.tsx`
- **Status**: NEW
- **Description**: A handful of files use `../` relative imports instead of the project-mandated `@/` absolute imports, violating CLAUDE.md's "absolute imports only" rule.
- **Evidence**:
  ```typescript
  import ParameterBar from '../ProcessingParameters/ParameterBar';  // ← relative
  ```
- **Impact**: Minor: relative imports work but are harder to refactor when moving files.
- **Suggested Fix**: Convert to `@/components/enhancement-pane/sections/ProcessingParameters/ParameterBar`.

---

### FE-27: TimeDisplay Redundant title + aria-label on `<time>` Element
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/TimeDisplay.tsx:115-130`
- **Status**: NEW
- **Description**: The `<time>` element sets both `aria-label` and `title` to the same formatted string. Screen readers may announce both, causing duplicate narration. The `title` tooltip duplicates what aria-label already conveys.
- **Evidence**:
  ```typescript
  <time aria-label={finalAriaLabel} title={displayString} ...>
    {displayString}
  </time>
  ```
- **Impact**: Minor: some screen readers announce the title as a separate tooltip. Creates a redundant auditory experience.
- **Suggested Fix**: Remove `title` or set it to a more descriptive tooltip that adds value beyond what's already in `aria-label`.

---

### FE-28: Accessibility Tests Verify Label Presence Only — Not Behaviour
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/library-management/accessibility.test.tsx:238-356`
- **Status**: NEW
- **Description**: Accessibility tests check that ARIA labels exist on interactive elements but do not verify focus management after modal open/close, keyboard navigation flows, screen reader announcement content, or WCAG contrast ratios.
- **Evidence**:
  ```typescript
  it('should have ARIA labels on interactive elements', () => {
    expect(screen.getByLabelText('Filter by genre')).toBeInTheDocument();
    // Missing: focus is on filter after open? Tab sequence correct? Escape closes modal?
  });
  ```
- **Impact**: The accessibility regressions captured in FE-16 (QueueSearchPanel) and FE-17 (GlobalSearch) would not be caught by the existing test suite.
- **Suggested Fix**: Add tests for keyboard interactions (Tab, Escape), focus trapping in modals, and `aria-live` announcements using `@testing-library/user-event`.

---

## Positive Findings

The Auralis frontend demonstrates strong patterns in many areas:
- **Transformer layer**: Explicit camelCase↔snake_case transformations in `api/transformers/` with null-safety (`?? undefined` pattern) — well done.
- **WebSocket type system**: The `AnyWebSocketMessage` discriminated union and existing type guards are thorough for the covered subset.
- **Loading state management**: `useRestAPI`'s inflight counter correctly handles concurrent requests (fixes #2489).
- **Test infrastructure**: 144 test files using Vitest, comprehensive `@testing-library` usage, dedicated test utilities.
- **Design token compliance**: Vast majority of components use `tokens.colors.*` throughout; the violations are exceptions not the norm.
- **Component decomposition**: EnhancementPane refactor from 585-line monolith into 10 focused components is excellent.
- **Request cancellation**: `useRestAPI` aborts in-flight requests on unmount — correctly implemented.

---

## Issue Index

| Finding | Issue | Severity |
|---------|-------|----------|
| FE-01 | #2532 | HIGH |
| FE-02 | #2533 | HIGH |
| FE-03 | #2534 | HIGH |
| FE-04 | #2535 | HIGH |
| FE-05 | #2536 | HIGH |
| FE-06 | #2537 | HIGH |
| FE-07 | #2538 | HIGH |
| FE-08 | #2539 | HIGH |
| FE-09 | #2540 | MEDIUM |
| FE-10 | Regression comment on #2139 | MEDIUM |
| FE-11 | #2541 | MEDIUM |
| FE-12 | #2542 | MEDIUM |
| FE-13 | #2543 | MEDIUM |
| FE-14 | #2544 | MEDIUM |
| FE-15 | #2545 | MEDIUM |
| FE-16 | #2546 | MEDIUM |
| FE-17 | #2547 | MEDIUM |
| FE-18 | #2548 | MEDIUM |
| FE-19 | #2549 | MEDIUM |
| FE-20 | #2550 | MEDIUM |
| FE-21 | #2551 | MEDIUM |
| FE-22 | #2558 | MEDIUM |
| FE-23 | #2552 | LOW |
| FE-24 | #2553 | LOW |
| FE-25 | #2554 | LOW |
| FE-26 | #2555 | LOW |
| FE-27 | #2556 | LOW |
| FE-28 | #2557 | LOW |

## Cross-references to Prior Issues

| Finding | Related Prior Issue |
|---------|-------------------|
| FE-07 | #2136 (sparse ARIA — specific drag/touch gap not yet covered) |
| FE-10 | #2139 (components >300 lines — Player.tsx regression) |
| FE-16 | #2136 (sparse ARIA — QueueSearchPanel modal specifics) |
| FE-23 | #2135 (hardcoded colors — specific file instance) |
