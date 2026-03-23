# Frontend Audit — 2026-03-20

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality, Redux State, Hook Correctness, TypeScript, Design System, API Client, Performance, Accessibility, Test Coverage
**Method**: 9 parallel dimension agents (Sonnet), followed by manual merge, deduplication, and cross-dimension analysis.

## Executive Summary

This audit reveals **12 HIGH**, **37 MEDIUM**, and **33 LOW** findings across all 9 dimensions. No CRITICAL findings were confirmed. Two MEDIUM findings (FE-72, FE-73) were marked STALE during validation.

**Most impactful clusters:**

1. **Accessibility gaps** (17 findings) — The track list, play buttons, drop zone, and progress bars lack keyboard navigation and ARIA labels. The entire library is mouse-only (FE-88). `text.tertiary` and `text.disabled` tokens fail WCAG AA contrast (FE-95).

2. **Hook correctness** (18 findings) — Stale closures, uncancelled timers, missing AbortControllers, and unstable callback references pervade the hooks layer. The most impactful: `usePlayNormal` dispatches to Redux after unmount (FE-77), `useEnhancementControl.toggleEnabled` races with WebSocket updates (FE-68), and `useVisualizationOptimization` stats never fire during playback (FE-75).

3. **Type safety erosion** (8 findings) — `WebSocketMessage<T = any>` propagates `any` through all subscription hooks (FE-56). The binary audio transport `pcm_binary` field exists only at runtime, not in the type system (FE-57). `EnhancementPreset` is silently widened to `string` in public APIs (FE-61).

4. **Design system drift** (9 findings) — `themeConfig.ts` maintains a parallel color system diverging from tokens (FE-63). `AnalysisExportService` renders Canvas with Material Design 2 colors (FE-64). The a11y contrast checker tests against wrong colors (FE-67).

5. **Test coverage gaps** (9 findings) — Invalid mock path silently disables TrackRow selection tests (FE-80). 742 lines of fingerprint hooks have zero tests (FE-81). Three Redux slices are entirely untested (FE-82).

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 12 |
| MEDIUM | 37 |
| LOW | 33 |
| **Total** | **82** |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 178 console.log statements | #2597 | STILL OPEN |
| FE-12: WebSocketContext propagates `any` | #2598 | FIXED |
| FE-14: 5 player components exceed 300 lines | #2600 | STILL OPEN (extended by FE-52) |
| FE-18: usePlayNormal passes handlers directly | #2604 | STILL OPEN |
| FE-19: Design system primitives use `as any` | #2605 | STILL OPEN |
| FE-23: AudioPlaybackEngine uses `window as any` | #2620 | STILL OPEN |
| FE-25: EnhancementContext isProcessing races | #2633 | STILL OPEN |
| FE-27: useSettingsDialog error state never rendered | #2635 | STILL OPEN |
| FE-28: queueSlice.setQueue([]) sets currentIndex to -1 | #2636 | STILL OPEN |
| FE-29: SettingsDialogHeader hardcodes color white | #2637 | STILL OPEN |
| FE-30: ScanStatusCard lacks aria-live region | #2638 | STILL OPEN |
| FE-31: Settings components use relative imports | #2639 | FIXED |
| FE-32: Six unused production dependencies | #2640 | STILL OPEN |
| FE-33: Nine duplicate Track interface definitions | #2662 | FIXED |
| FE-34: useSearchLogic fetches entire library per keystroke | — | STILL OPEN |
| FE-35: Queue context menus build incomplete track objects | — | STILL OPEN |
| FE-36: useQueue hook accepts `any` for all track actions | — | STILL OPEN |
| FE-37: useBatchOperations sequential raw fetch | — | STILL OPEN |
| FE-38: StandardizedAPIClient retries non-idempotent requests | — | STILL OPEN |
| FE-39: Custom modal dialogs lack role="dialog" | — | STILL OPEN |
| FE-40: usePlaybackState bypasses typed PlayerStateData | — | STILL OPEN |
| FE-41: EditMetadataDialog hardcodes hex colors | #2651 | STILL OPEN |
| FE-42: SimilarityVisualization async effect lacks abort | #2645 | STILL OPEN |
| FE-43: useMasteringRecommendation mutates useState cache | #2695 | STILL OPEN |
| FE-44: useKeyboardShortcuts recomputes shortcuts array | #2696 | STILL OPEN |
| FE-45: usePlayerAPI.playTrack depends on entire playerState | #2697 | STILL OPEN |
| FE-46: usePlayNormal subscribes to WS inside playNormal() | #2604 | STILL OPEN |
| FE-47: QueuePanel renders full queue without virtualization | #2698 | STILL OPEN |
| FE-48: usePlaybackProgress subscribes to entire state.player | #2699 | STILL OPEN |
| FE-49: selectRemainingTime/selectTotalQueueTime non-memoized | #2700 | STILL OPEN |
| FE-50: useVisualizationOptimization empty dep array | #2701 | STILL OPEN |
| FE-51: useVisualizationOptimization non-null asserted refs | #2702 | STILL OPEN |
| ArtworkResponse frontend type mismatch | #2627 | STILL OPEN |
| Hardcoded CSS colors in 4 source files | #2655 | STILL OPEN |
| Stale CRA proxy field in package.json | #2652 | STILL OPEN |
| Vite loader script embeds 6 console calls | #2656 | STILL OPEN |
| Missing regression tests for frontend fixes | #2669 | STILL OPEN |
| Vitest deprecated config options | #2673 | STILL OPEN |

---

## New Findings

### HIGH

---

### FE-52: Six additional components exceed 300-line guideline
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `AlbumCharacterPane.tsx` (1111 lines), `QueuePanel.tsx` (750), `EnhancementInspectionLayer.tsx` (740), `CacheManagementPanel.tsx` (703), `QueueSearchPanel.tsx` (671), `QueueRecommendationsPanel.tsx` (663)
- **Status**: NEW (extends FE-14)
- **Description**: Six components far exceed the 300-line guideline. `AlbumCharacterPane.tsx` at 1111 lines contains six independently renderable sub-components (`FloatingParticles`, `GlowingArc`, `EnergyField`, `WaveformVisualization`, `RotatingDescription`, `CharacterTags`) and an exported hook (`usePlaybackWithDecay`).
- **Impact**: Monolithic files resist testing, review, and reuse. Changes to one sub-component force re-evaluation of the entire file.
- **Suggested Fix**: Extract sub-components and hooks into separate files within existing directories.

---

### FE-53: `EnhancementSection` defined via `useCallback` causes subtree remount on every toggle
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:790-807`
- **Status**: NEW
- **Description**: `EnhancementSection` is defined as `const EnhancementSection = useCallback(() => (...), [deps])` and used as `<EnhancementSection />`. Because `useCallback` returns a new function reference when deps change, React treats it as a different component type and unmounts/remounts the subtree on every enhancement toggle.
- **Evidence**:
  ```tsx
  const EnhancementSection = useCallback(() => (
    <Box sx={{ ... }}>
      <EnhancementToggle isEnabled={isEnhancementEnabled} onToggle={onEnhancementToggle ?? (() => {})} />
    </Box>
  ), [isEnhancementEnabled, onEnhancementToggle]);
  // Used as: <EnhancementSection />  — lines 840, 873, 932, 962
  ```
- **Impact**: Focus is lost mid-interaction. Animation state resets. React StrictMode double-effects fire on every toggle.
- **Suggested Fix**: Define as a named component outside `AlbumCharacterPane`, or inline the JSX directly.

---

### FE-54: `QueuePanel` fires PUT reorder API on every `dragover` event without debounce
- **Severity**: HIGH
- **Dimension**: Component Quality / Performance
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:320-323`
- **Status**: NEW
- **Description**: `onDragOver` calls `handleReorderTrack()` which issues `PUT /api/player/queue/reorder`. The native `dragover` fires ~60 fps — a single drag can produce 30-100 concurrent PUT requests.
- **Evidence**:
  ```tsx
  onDragOver={(toIndex) => {
    if (draggingIndex !== null && draggingIndex !== toIndex) {
      handleReorderTrack(draggingIndex, toIndex); // fires PUT each dragover tick
    }
  }}
  ```
- **Impact**: Backend flooded with concurrent reorder requests that may arrive out of order.
- **Suggested Fix**: Track intended position in a ref during drag; commit reorder only on `onDragEnd`.

---

### FE-55: `WebSocketMessage<T = any>` base type defaults `data` to `any`, defeating type narrowing
- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/websocket.ts:61`, `hooks/websocket/useWebSocketSubscription.ts:167-180`
- **Status**: NEW
- **Description**: `WebSocketMessage<T = any>` uses `any` as default for `T`. `Extract<WebSocketMessage, {type: T}>` always resolves to `WebSocketMessage<any>`, making subscription hooks receive `data: any`.
- **Evidence**:
  ```ts
  export interface WebSocketMessage<T = any> {
    type: WebSocketMessageType;
    data: T;  // defaults to any
  }
  ```
- **Impact**: All `useWebSocketMessage` callbacks receive untyped `data`. Type errors in data field access are silently suppressed.
- **Suggested Fix**: Change default to `unknown`. Use discriminated union `AnyWebSocketMessage` for `Extract`.

---

### FE-56: `pcm_binary` binary-transport field absent from `AudioChunkMessage` interface
- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/websocket.ts:398-410`, `contexts/WebSocketContext.tsx:258-265`
- **Status**: NEW
- **Description**: `WebSocketContext` synthesizes an `audio_chunk` message with `pcm_binary: ArrayBuffer` injected at runtime. This field doesn't exist in `AudioChunkMessage.data`, forcing `combined: any` and `decodeAudioChunkMessage(message: any)`.
- **Impact**: TypeScript cannot validate audio chunk message consumers. Accidental use of base64 vs binary path is invisible.
- **Suggested Fix**: Add `pcm_binary?: ArrayBuffer` to `AudioChunkMessage.data`. Remove `any` casts.

---

### FE-57: `themeConfig.ts` maintains duplicate color palette diverging from `tokens.ts`
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:1-87`
- **Status**: NEW
- **Description**: `darkColors`, `lightColors`, and `gradients` are defined independently from `tokens.ts`. The slider override uses `#667eea` (legacy purple) instead of `tokens.colors.accent.primary` (`#7366F0`). Light-theme semantic colors diverge from `tokens.colors.semantic.*`.
- **Impact**: Components using `useTheme().colors` receive values that don't match tokens. Visual inconsistency.
- **Suggested Fix**: Derive `darkColors`/`lightColors` from `tokens.*` values.

---

### FE-58: `AnalysisExportService` Canvas rendering uses fully hardcoded Material Design 2 colors
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/services/AnalysisExportService.ts:685-803`
- **Status**: NEW
- **Description**: All Canvas 2D rendering uses hardcoded hex values (`#4FC3F7`, `#1976D2`, `#FFB74D`, `#FF6B6B`) completely outside the Auralis palette. The `tokens.colors.audioSemantic.*` system designed for this purpose is ignored.
- **Impact**: Exported analysis images use a completely different color palette from the UI.
- **Suggested Fix**: Replace with `tokens.colors.audioSemantic.*` values.

---

### FE-59: `TrackRowPlayButton` missing `aria-label` — icon-only unlabelled button
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRowPlayButton.tsx:22-26`
- **Status**: NEW
- **Description**: `PlayButton` wraps a `PlayArrow`/`Pause` icon with no `aria-label`. Screen readers announce a generic or empty label.
- **Impact**: Screen-reader users cannot determine whether the button plays or pauses.
- **Suggested Fix**: Add `aria-label={isCurrent && isPlaying ? 'Pause' : 'Play'} ${trackTitle}`.

---

### FE-60: `DropZone` is entirely mouse-only — no keyboard activation or ARIA
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/DropZone/DropZone.tsx:74-88`
- **Status**: NEW
- **Description**: `DropZone` responds only to mouse drag/click. No `tabIndex`, `role`, `aria-label`, or `onKeyDown`.
- **Impact**: Keyboard and screen-reader users cannot import music folders via the drop zone.
- **Suggested Fix**: Add `tabIndex={0}`, `role="button"`, `aria-label`, and `onKeyDown` for Enter/Space.

---

### FE-61: Invalid mock path in `TrackRow.test.tsx` silently disables `useTrackSelection` mock
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/library/__tests__/TrackRow.test.tsx:17-20`
- **Status**: NEW
- **Description**: Test imports from `@/hooks/library/useTrackSelection` but mocks `'../../../hooks/useTrackSelection'` — a path that doesn't exist. All `vi.mocked().mockReturnValue()` calls across 6 tests have no effect.
- **Impact**: Selection-state branches tested against uncontrolled hook state. Tests may pass or fail nondeterministically.
- **Suggested Fix**: Change mock path to `vi.mock('@/hooks/library/useTrackSelection')`.

---

### FE-62: Fingerprint hook subsystem entirely untested (742 lines, zero tests)
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/`
- **Status**: NEW
- **Description**: Four hooks — `useAlbumFingerprint` (128 lines), `useFingerprintCache` (277 lines), `useSimilarTracks` (221 lines), `useTrackFingerprint` (116 lines) — have zero direct tests. `useFingerprintCache` with LRU/expiry logic has no test surface at all.
- **Impact**: Cache eviction bugs and race conditions in the similarity feature have no regression safety net.
- **Suggested Fix**: Add `renderHook` tests for cache hit/miss/expiry, loading/error states, and result shapes.

---

### MEDIUM

---

### FE-63: Module-level `document.createElement` injects duplicate `<style>` tags on HMR
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `EnhancementInspectionLayer.tsx:732-738`, `EnhancementPane.tsx:235-248`, `PlayerEnhancementPanel.tsx:385-392`
- **Status**: NEW
- **Description**: Three files inject `@keyframes spin` via `document.head.appendChild(styleSheet)` at module evaluation time. Never removed on unmount. Duplicated on every HMR reload.
- **Suggested Fix**: Move to `useEffect` with cleanup, or use MUI's `keyframes` helper.

---

### FE-64: `isEnhancementEnabled` prop drilled through 3 intermediate components
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `ComfortableApp` -> `CozyLibraryView` -> `LibraryViewRouter` -> `AlbumCharacterPane`
- **Status**: NEW
- **Description**: Neither `CozyLibraryView` nor `LibraryViewRouter` consumes these values — they are pure conduits. `EnhancementContext` already exists and is provided at `App.tsx` level.
- **Suggested Fix**: Read enhancement state from `EnhancementContext` directly in `AlbumCharacterPane`.

---

### FE-65: `ConnectionStatusIndicator` stale-closure timer + async setState without mount guard
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/ConnectionStatusIndicator.tsx:87-135`
- **Status**: NEW
- **Description**: Cleanup reads `autoHideTimer` from closure (always stale). `setInterval` with async `fetch('/api/health')` calls `setStatus` without mount guard.
- **Suggested Fix**: Replace `useState` timer with `useRef`. Add `mountedRef` guard.

---

### FE-66: Uncleared `setTimeout` inside `setInterval` in `RotatingDescription`
- **Severity**: MEDIUM
- **Dimension**: Component Quality / Performance
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:626-635`
- **Status**: NEW
- **Description**: `setTimeout` scheduled inside `setInterval` is never stored or cancelled. On unmount, pending 400ms timeout calls `setCurrentIndex`/`setIsVisible` on unmounted component.
- **Suggested Fix**: Store timeout in ref, cancel in cleanup.

---

### FE-67: `player.duration` duplicates `player.currentTrack.duration`, creating divergence risk
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:37-52,104-107,132-140`
- **Status**: NEW
- **Description**: `PlayerState` stores `duration` as top-level field alongside `currentTrack`. `setDuration` can update one without the other.
- **Impact**: `selectDuration` and `selectCurrentTrack` disagree on duration after independent `setDuration` calls.
- **Suggested Fix**: Remove top-level `duration`. Derive from `currentTrack?.duration ?? 0` in a selector.

---

### FE-68: `selectAppSnapshot` hardcodes `isLoading: false` and `hasErrors: false`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/selectors/index.ts:258-268`
- **Status**: NEW
- **Description**: Memoized selector unconditionally returns `isLoading: false, hasErrors: false`, ignoring all actual loading and error state.
- **Impact**: Consumers of `selectAppSnapshot.isLoading` never see loading spinners or error states.
- **Suggested Fix**: Derive from actual slice loading/error fields.

---

### FE-69: Specialized WS protocol hooks spawn duplicate reconnect subscriptions on every render
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketProtocol.ts:168-223`
- **Status**: NEW
- **Description**: Seven specialized hooks (`useCacheStatsUpdates`, `usePlayerStateUpdates`, etc.) each independently instantiate `useWebSocketProtocol`. Each `client.onConnectionChange()` call registers an additional listener without cleanup.
- **Impact**: Components that remount frequently accumulate stale listener registrations.
- **Suggested Fix**: Extract send/subscribe once via singleton, or accept pre-created pair.

---

### FE-70: `onConnectionChange`/`onError` callback props in `useWebSocketProtocol` dep array cause effect churn
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketProtocol.ts:92`
- **Status**: NEW
- **Description**: Effect depends on `onConnectionChange` and `onError` — typically inline arrows that change identity every render. Effect tears down and recreates WS subscription on every render.
- **Impact**: Connection state updates can be lost during unsubscribe/resubscribe window.
- **Suggested Fix**: Use ref-indirection pattern for callback props.

---

### FE-71: Drift-correction `setTimeout` in `usePlayerStreaming` never cancelled
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStreaming.ts:272-280`
- **Status**: NEW
- **Description**: Anonymous `setTimeout` resets `audioElement.playbackRate` to 1.0 after drift correction. Not stored in ref, not clearable. Multiple overlapping timeouts on rapid seek events.
- **Suggested Fix**: Store in `useRef`, clear on cleanup and before scheduling new one.

---

### FE-72: `toggleEnabled` closes over stale `state.enabled` despite in-flight guard
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:184-212`
- **Status**: NEW
- **Description**: If WebSocket delivers `enhancement_settings_changed` between click and optimistic update, `newEnabled` is computed from stale closure value.
- **Impact**: Toggle can flip enhancement to the wrong state if WS update races user click.
- **Suggested Fix**: Use functional state updater or `stateRef` pattern.

---

### FE-73: `useAudioVisualization` interval can leak on rapid `isAudioActive` toggle
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/audio/useAudioVisualization.ts:160-175`
- **Status**: NEW
- **Description**: `setInterval` checking for audio context stores handle in local var. Cleanup works per-invocation but side effects (ref assignments) can fire after unmount.
- **Suggested Fix**: Store interval ID in ref for deterministic cleanup.

---

### FE-74: `useLibraryQuery.executeQuery` uses stale `isLoading` in deduplication guard
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:221-278`
- **Status**: NEW
- **Description**: `isLoading` not in `useCallback` deps but read from closure. Stale value can allow duplicate requests through the guard.
- **Suggested Fix**: Replace with `isFetchingRef`.

---

### FE-75: `useVisualizationOptimization` stats interval restarts on every render
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useVisualizationOptimization.ts:75-90`
- **Status**: NEW
- **Description**: `onStatsUpdate` callback in dep array changes identity on every render. Timer is reset before it fires, so stats never update during active playback (~30fps re-renders).
- **Suggested Fix**: Store `onStatsUpdate` in ref, remove from dep array.

---

### FE-76: `useOptimisticUpdate.execute` recreated on every render when `options` is inline
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useOptimisticUpdate.ts:26-57`
- **Status**: NEW
- **Description**: `useCallback([asyncOperation, options])` — `options` is an inline object that changes identity every render, defeating memoization.
- **Suggested Fix**: Destructure options, use refs for callbacks.

---

### FE-77: `usePlayNormal.playNormal` dispatches to Redux after unmount via uncancellable fetch
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:449-460`
- **Status**: NEW
- **Description**: `fetch()` to `/api/library/tracks/${trackId}` has no `AbortController`. `dispatch(setCurrentTrack(...))` fires after unmount, corrupting Redux with stale data. Same pattern in `usePlayEnhanced.playEnhanced` at line 583.
- **Impact**: After rapid track changes, player bar shows wrong track.
- **Suggested Fix**: Add `AbortController` signal or `isMountedRef` guard.

---

### FE-78: `usePlayerAPI` WebSocket handler overwrites optimistic state before server confirms
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts:272-303`
- **Status**: NEW
- **Description**: `play()` optimistically sets `isPlaying: true`. Stale WS `player_state` broadcast can overwrite it back to `false` before the play command takes effect.
- **Impact**: UI flicker — play button briefly shows "paused" after click, 200-500ms.
- **Suggested Fix**: Track `pendingCommand` ref; ignore WS updates while command is in-flight.

---

### FE-79: `createWebSocketMiddleware` accepts `protocolClient: any`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/store/middleware/websocketMiddleware.ts:279`
- **Status**: NEW
- **Description**: Redux middleware factory accepts `any`, erasing `WebSocketProtocolClient` interface at the middleware boundary.
- **Suggested Fix**: Type as `IProtocolClient` interface extracted from `WebSocketProtocolClient`.

---

### FE-80: `OptimisticUpdate.action`/`.rollback` typed `any`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/store/middleware/websocketMiddleware.ts:396-399`
- **Status**: NEW
- **Description**: Any value can be dispatched as a Redux action without TypeScript catching it.
- **Suggested Fix**: Type as `UnknownAction`.

---

### FE-81: `message.payload as any` discards `CacheStats`/`CacheHealth` contracts
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/store/middleware/websocketMiddleware.ts:172-182`
- **Status**: NEW
- **Description**: CACHE_STATS/CACHE_STATUS handlers cast payload to `any` before dispatching to typed reducers. Malformed payloads dispatched without complaint.
- **Suggested Fix**: Add narrow type guards, remove `as any`.

---

### FE-82: `EnhancementPreset` union silently widened to `string` in public APIs
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `EnhancementContext.tsx:22`, `usePlayEnhanced.ts:79`, `websocket.ts:375`
- **Status**: NEW
- **Description**: `EnhancementPreset` is `'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy'` but three API surfaces accept `preset: string`.
- **Impact**: Typos like `'adpative'` pass without error. Backend receives invalid preset.
- **Suggested Fix**: Replace `string` with `EnhancementPreset` at all three locations.

---

### FE-83: `ALL_MESSAGE_TYPES` omits 7 of 32 `WebSocketMessageType` values
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/websocket.ts:600-626`
- **Status**: NEW
- **Description**: Missing: `fingerprint_progress`, `seek_started`, `audio_stream_start`, `audio_stream_end`, `audio_chunk`, `audio_chunk_meta`, `audio_stream_error`. Type is `WebSocketMessageType[]` not exhaustive tuple.
- **Impact**: Subscription managers and logging silently skip all audio streaming messages.
- **Suggested Fix**: Add missing strings. Add compile-time exhaustiveness check.

---

### FE-84: `StreamingProgressBar` and `StreamingErrorBoundary` — pervasive hardcoded typography
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `StreamingProgressBar.tsx:296-456`, `StreamingErrorBoundary.tsx:366-516`
- **Status**: NEW
- **Description**: 30+ instances of hardcoded `fontSize`, `fontWeight`, `lineHeight`, `borderRadius` — none using tokens.
- **Suggested Fix**: Replace with `tokens.typography.*` and `tokens.borderRadius.*`.

---

### FE-85: `contrastChecker.ts` defines independent palette not derived from tokens
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/a11y/contrastChecker.ts:301-326`
- **Status**: NEW
- **Description**: `accessiblePalette.primary` is `#0066cc` while tokens says `#7366F0`. The a11y checker tests against wrong colors.
- **Suggested Fix**: Derive from `tokens.colors.*`.

---

### FE-86: Grid/Playlist styled components use `theme.palette.*` instead of tokens
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `Grid.styles.ts:62-96`, `DroppablePlaylist.styles.ts:31-57`, `DraggableTrackRow.tsx:23`
- **Status**: NEW
- **Description**: `theme.palette.primary.main` / `theme.palette.text.secondary` bypass design tokens. MUI palette already drifts from tokens (FE-57).
- **Suggested Fix**: Replace with `tokens.colors.*` equivalents.

---

### FE-87: Raw `@media` breakpoints inconsistent with `tokens.breakpoints`
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `Player.tsx:457`, `AlbumGrid.tsx:128-147`, `DetailViewHeader.tsx:54,66`, `TrackRow.styles.ts:203`
- **Status**: NEW
- **Description**: Components use `768px`, `640px`, `960px` instead of `tokens.breakpoints.sm` (600px), `.md` (900px).
- **Suggested Fix**: Replace with `tokens.breakpoints.*` references.

---

### FE-88: `useLibraryWithStats.handleScanFolder` uses blocking `alert()`/`prompt()`
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:268-298`
- **Status**: NEW
- **Description**: Sibling hook `useLibraryData` already fixed this (comment notes "fixes #2359"), but `useLibraryWithStats` still uses `prompt()` and `alert()`.
- **Suggested Fix**: Mirror `useLibraryData` pattern — use `useToast()`.

---

### FE-89: `useLibraryWithStats.loadMore` uses `setTimeout(0)` anti-pattern
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:220-228`
- **Status**: NEW
- **Description**: Extracts offset via `setOffset` updater + `setTimeout(0)` instead of mirroring in `useRef` (as `useLibraryData` correctly does).
- **Suggested Fix**: Use `useRef` for offset mirror, drop `setTimeout`.

---

### FE-90: `apiRequest` utility has no `AbortSignal` support
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:46-103`
- **Status**: NEW
- **Description**: All service-layer callers using `apiRequest` cannot cancel in-flight requests on unmount.
- **Impact**: setState-after-unmount warnings for components using service functions in `useEffect`.
- **Suggested Fix**: Add optional `signal?: AbortSignal` to `RequestOptions`.

---

### FE-91: `AudioReactiveStarfield` creates new prop object on every audio render (30fps)
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/background/AudioReactiveStarfield.tsx:47-54`
- **Status**: NEW
- **Description**: Plain object literal `audioReactivity` passed as prop to `StarfieldBackground` — new reference every render at 30fps. Triggers `useEffect([audioReactivity])` 30x/sec.
- **Suggested Fix**: `useMemo` the object + `React.memo` on `StarfieldBackground`.

---

### FE-92: `CacheStatsDashboard` doubles polling with redundant `setInterval`
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `CacheStatsDashboard.tsx:188-197`, `useStandardizedAPI.ts:340-344`
- **Status**: NEW
- **Description**: `useCacheStats()` polls every 5s. `CacheStatsDashboard` adds its own 5s interval. Result: 2 HTTP requests every 5 seconds.
- **Suggested Fix**: Remove component-level interval.

---

### FE-93: `useCacheStats`/`useCacheHealth` create independent intervals — should use React Query
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:294-407`
- **Status**: NEW
- **Description**: Each mounted consumer starts its own timer. With 4 components visible, up to 4 concurrent polling loops run. `@tanstack/react-query` is already installed.
- **Suggested Fix**: Convert to `useQuery` with shared query key.

---

### FE-94: No route-level code splitting — all views in single app chunk
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `App.tsx`, `ComfortableApp.tsx`, `vite.config.mts:126-145`
- **Status**: NEW
- **Description**: `chunkSizeWarningLimit` raised to 1000kB to suppress warning. `performance/lazyLoader.tsx` infrastructure built but unused. All heavy views statically imported.
- **Suggested Fix**: Apply `React.lazy()` + `<Suspense>` at panel/dialog boundaries.

---

### FE-95: `EnhancementIdentityLayer` `role="button"` div has no `onKeyDown`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/enhancement/EnhancementIdentityLayer.tsx:94-105`
- **Status**: NEW
- **Description**: `role="button"` + `tabIndex={0}` but only `onClick` — keyboard users cannot activate with Enter/Space.
- **Suggested Fix**: Add `onKeyDown` handler + `aria-label`.

---

### FE-96: `StreamingProgressBar` progress bars have no `role="progressbar"` or ARIA
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/enhancement/StreamingProgressBar.tsx:148-279`
- **Status**: NEW
- **Description**: Three progress bars rendered as plain `<div>` with no ARIA value attributes.
- **Suggested Fix**: Add `role="progressbar"`, `aria-valuenow/min/max`, `aria-label`.

---

### FE-97: `QueuePanel` clear uses native `confirm()` — inaccessible and blocks event loop
- **Severity**: MEDIUM
- **Dimension**: Accessibility / Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:172`
- **Status**: NEW
- **Description**: Synchronous browser `confirm()` blocks JS thread, cannot be themed/tested, inconsistent with custom `ConfirmationModal` elsewhere.
- **Suggested Fix**: Replace with custom confirmation dialog using `role="dialog"` + `aria-modal="true"`.

---

### FE-98: `outline: 'none'` on primary buttons without `:focus-visible` replacement
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `PlaybackControlsStyles.ts:47,87`, `Player.tsx:507`, `AlbumActionButtons.tsx:62`, `ArtistHeader.tsx:111`, `AlbumGrid.tsx:201`
- **Status**: NEW
- **Description**: Multiple button styles remove outline without providing focus-visible alternative. Keyboard-only users see no focus indicator.
- **Impact**: Fails WCAG 2.1 SC 2.4.7 (Focus Visible).
- **Suggested Fix**: Use `:focus-visible` CSS selector instead of blanket `outline: none`.

---

### FE-99: `text.tertiary` (2.7:1) and `text.disabled` (1.6:1) tokens fail WCAG AA contrast
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/design-system/tokens.ts:105-112`
- **Status**: NEW
- **Description**: Against `bg.level1` (`#101729`): `text.tertiary` at 45% white = 2.7:1 (fails 4.5:1 AA); `text.disabled` at 25% white = 1.6:1 (fails all thresholds).
- **Impact**: Users with low vision cannot read track durations and secondary metadata.
- **Suggested Fix**: Increase `text.tertiary` to at least `rgba(255,255,255,0.60)`.

---

### FE-100: `TrackRow` `RowContainer` not keyboard-focusable — click-only
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:100-147`
- **Status**: NEW
- **Description**: `RowContainer` handles `onClick`/`onDoubleClick`/`onContextMenu` but has no `tabIndex`, `role`, or `onKeyDown`. The entire library track list is not keyboard navigable.
- **Impact**: Users cannot play, select, or open context menu for any track via keyboard.
- **Suggested Fix**: Add `tabIndex={0}`, `role="row"`, `aria-label`, and `onKeyDown` handler.

---

### FE-101: `SelectableTrackRow` checkbox hidden from keyboard users
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/SelectableTrackRow.styles.ts:28-42`
- **Status**: NEW
- **Description**: `StyledCheckbox` has `opacity: 0` by default — no `:focus-visible` recovery. Keyboard-driven multi-select impossible.
- **Suggested Fix**: Apply `:focus-visible { opacity: 1 }` on the checkbox.

---

### FE-102: `MediaCardOverlay` and `PlayOverlay` play buttons missing `aria-label`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `MediaCardOverlay.tsx:69-84`, `PlayOverlay.tsx:36-51`
- **Status**: NEW
- **Description**: Two separate play overlay components render `IconButton` with `PlayArrow` icon and no `aria-label`.
- **Suggested Fix**: Add `aria-label={`Play ${title}`}` and thread title from parent.

---

### FE-103: `SimilarTracksModal` close button and `AlbumActionButtons` icon buttons missing `aria-label`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `SimilarTracksModal.tsx:146-157`, `AlbumActionButtons.tsx:108-147`
- **Status**: NEW
- **Description**: Close `IconButton` and "Add to Queue"/"More Options" icon buttons have `Tooltip` but no `aria-label`.
- **Suggested Fix**: Add `aria-label` to each `IconButton`.

---

### FE-104: Three Redux slices (`queueSlice`, `connectionSlice`, `cacheSlice`) have no tests
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/store/slices/`
- **Status**: NEW
- **Description**: 697 combined lines, 14+ reducers, zero test coverage. Only `playerSlice` has a test file.
- **Suggested Fix**: Add slice test files with standard reducer testing patterns.

---

### FE-105: 80 uses of `fireEvent.click` instead of `userEvent`
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: Multiple test files across `src/components/`
- **Status**: NEW
- **Description**: `fireEvent` dispatches raw synthetic DOM events without full browser event sequence. `@testing-library/user-event` is installed and used in integration tests (194 usages) but not in unit tests.
- **Suggested Fix**: Migrate to `await user.click(element)` using `userEvent.setup()`.

---

### FE-106: Stale comment implies 20 player tests are skipped — they're not
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/player-controls/player-controls.test.tsx:1-12`
- **Status**: NEW
- **Description**: Header says "PlayerBarV2 does not exist yet" but it's fully implemented. Tests are NOT `describe.skip`. Creates maintainer confusion.
- **Suggested Fix**: Remove stale comment.

---

### FE-107: Nine significant hooks have no unit tests (1,400+ lines)
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `useLibraryWithStats` (380), `useVisualizationOptimization` (408), `useEnhancedPlaybackShortcuts` (177), `useTrackSelection` (151), `useScanProgress` (92), `useOptimisticUpdate` (75), `useScrollAnimation` (200), and others
- **Status**: NEW
- **Description**: Beyond fingerprint cluster (FE-62), nine additional non-trivial hooks lack tests. Combined 1,400+ untested lines against 85% coverage threshold.
- **Suggested Fix**: Prioritize `useOptimisticUpdate`, `useScanProgress`, and `useTrackSelection` as first targets.

---

### LOW

---

### FE-108: Reorderable queue list uses index-inclusive composite key
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/QueueManager.tsx:254`
- **Status**: NEW
- **Description**: `key={track.id}-${index}` — index changes on reorder, causing remounts instead of reuse.
- **Suggested Fix**: Use `key={track.id}` alone.

---

### FE-109: Deprecated `onKeyPress` in 3 files
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `QueueSearchPanel.tsx:299`, `EditPlaylistDialog.tsx:68`, `PlaylistFormFields.tsx:38`
- **Status**: NEW
- **Description**: `onKeyPress` removed from Web standard, fails for Space in some browsers.
- **Suggested Fix**: Replace with `onKeyDown`.

---

### FE-110: `QUEUE_ADD` WebSocket handler silently ignores positional `index`
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/middleware/websocketMiddleware.ts:136-146`
- **Status**: NEW
- **Description**: Both `if (index !== undefined)` branches dispatch identical `addTrack(track)`. Positional inserts treated as appends.
- **Impact**: Queue order diverges from backend.
- **Suggested Fix**: Add `insertTrackAt` reducer, or dispatch reorder after append.

---

### FE-111: `useQueueTimeRemaining` subscribes to entire queue slice, returns new object every render
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:397-411`
- **Status**: NEW
- **Description**: Inline O(n) computation without `useMemo`. Returns `{ total, formatted }` — new object every render.
- **Suggested Fix**: Use existing memoized `selectRemainingTime` selector via `useSelector`.

---

### FE-112: `useWebSocketStatus` always returns initial snapshot — never updates
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketSubscription.ts:206-230`
- **Status**: NEW
- **Description**: Module-level callback overwritten on each mount. Only last mounted consumer receives updates.
- **Suggested Fix**: Replace with pub-sub or context approach.

---

### FE-113: Layer 2 effect in `usePlayerStreaming` depends on `driftThreshold` causing unnecessary resubscriptions
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStreaming.ts:255-314`
- **Status**: NEW

---

### FE-114: `useQueueHistory` refetches when `api` object identity changes
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:143-162`
- **Status**: NEW
- **Description**: `useEffect([api])` — if `api` gets new identity, history resets.
- **Suggested Fix**: Destructure `get` from `useRestAPI()`, use as dep.

---

### FE-115: `useQueueRecommendations` returns unstable utility function references
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueRecommendations.ts:191-219`
- **Status**: NEW
- **Description**: `getRecommendationsFor`, `getByArtist`, `getAlbumsByArtist` not wrapped in `useCallback`.

---

### FE-116: `useQueueStatistics` returns unstable functions
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueStatistics.ts:189-200`
- **Status**: NEW

---

### FE-117: `useLibraryQuery.executeQuery` creates `AbortController` never connected to fetch
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:236-240`
- **Status**: NEW
- **Description**: `AbortController` stored in ref but signal never passed to `api.get()`.

---

### FE-118: `useSynchronizedVisualizations` rAF loop restarts on every `visualizations` array change
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useVisualizationOptimization.ts:387-400`
- **Status**: NEW

---

### FE-119: `useStaggerAnimation` setTimeout callbacks never cancelled on unmount
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useScrollAnimation.ts:140-142`
- **Status**: NEW

---

### FE-120: `Window.electronAPI` accessed via `as any` in 3 files — no type declaration
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `useLibraryWithStats.ts:118,260`, `useLibraryData.ts:71,184`, `useSettingsDialog.ts:96-98`
- **Status**: NEW
- **Suggested Fix**: Add `Window` augmentation in `vite-env.d.ts`. Centralise `isElectron()` check.

---

### FE-121: `SwitchVariant` and `Button.styles.ts` hardcode `rgba` colors available as tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `SwitchVariant.tsx:44-53`, `Button.styles.ts:41,92`
- **Status**: NEW

---

### FE-122: 44 hardcoded `fontWeight` + 82 hardcoded `fontSize` instances across components
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `ArtistList.styles.ts`, `TrackRow.styles.ts`, `FoldersList.tsx`, `PlayerEnhancementPanel.tsx`, and others
- **Status**: NEW
- **Description**: `17px` in `ArtistList.styles.ts` not in token scale. All values have token equivalents.

---

### FE-123: 140+ relative `../` imports that should use `@/` absolute paths
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: Components, contexts, services across `src/`
- **Status**: NEW
- **Suggested Fix**: Add lint rule `no-relative-parent-imports`, run codemod.

---

### FE-124: `useRestAPI` stale-response detection leaves response body unconsumed
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:107-116`
- **Status**: NEW
- **Description**: `StaleRequestError` thrown before `response.json()`. HTTP body stream held open until GC.
- **Suggested Fix**: Call `response.body?.cancel()` before throwing.

---

### FE-125: `RealTimeAnalysisStream.connect()` defaults to wrong port (8080 vs 8765)
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/RealTimeAnalysisStream.ts:186`
- **Status**: NEW
- **Description**: Default `ws://localhost:8080/analysis-stream` while everything else uses `:8765`.
- **Suggested Fix**: Default to `getWsUrl('/analysis-stream')`.

---

### FE-126: `StandardizedAPIClient.getPaginated` produces malformed URLs with existing query params
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:363-371`
- **Status**: NEW
- **Description**: Naively appends `?limit=&offset=` — creates two `?` characters if endpoint already has params.
- **Suggested Fix**: Use `URLSearchParams` with `URL` constructor.

---

### FE-127: `processAudio` retries non-idempotent POST 3 times
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/services/processingService.ts:199-211`
- **Status**: NEW
- **Description**: Distinct from FE-38 (which covers `StandardizedAPIClient`). This directly wraps POST in `retryWithBackoff`.
- **Impact**: Duplicate audio processing jobs on transient failure after server accepts.

---

### FE-128: `TrackRowAlbumArt` renders `<img>` without `loading="lazy"`
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRowAlbumArt.tsx:28`
- **Status**: NEW

---

### FE-129: `QueuePanel` `<ul>` has orphaned `role="option"` children with no `listbox` owner
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel.tsx:296-340`
- **Status**: NEW
- **Description**: `role="option"` items require parent `listbox` — `<ul>` has no `role`.
- **Suggested Fix**: Add `role="listbox"` to `<ul>` or change items to `role="listitem"`.

---

### FE-130: `PlayerControls` (shared) seek bar has no `role="slider"` or ARIA
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/PlayerControls.tsx:218-256`
- **Status**: NEW

---

### FE-131: `BatchActionButton` passes `title` to Tooltip but not `aria-label` to button
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Controls/BatchActionButton.tsx:27-33`
- **Status**: NEW

---

### FE-132: `TrackList` `role="button"` items use wrong ARIA (`aria-pressed` instead of `aria-selected`)
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/TrackList.tsx:155-190`
- **Status**: NEW

---

### FE-133: Non-awaited `act()` in WebSocket reconnect tests may miss state flush
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/contexts/__tests__/WebSocketContext.reconnect.test.tsx:127-271`
- **Status**: NEW

---

### FE-134: `vitest.config.ts` `globals` option has invalid type (array instead of boolean)
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/vitest.config.ts:33`
- **Status**: NEW
- **Description**: `globals: ['describe', 'it', ...]` — works due to array truthiness but not a valid type per Vitest 3.x.
- **Suggested Fix**: Change to `globals: true`.

---

### FE-135: Five skipped WCAG color contrast tests with no re-enable plan
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/a11y/__tests__/a11y.test.ts:277-432`
- **Status**: NEW

---

## Relationships & Shared Root Causes

1. **`any` propagation chain**: FE-55 (WebSocketMessage default) -> FE-56 (pcm_binary typed any) -> FE-79 (middleware any) -> FE-81 (payload as any). Fixing the WebSocketMessage base type would tighten the entire chain.

2. **Ref-vs-state anti-pattern**: FE-66 (RotatingDescription), FE-65 (ConnectionStatusIndicator), FE-71 (drift setTimeout), FE-73 (audio interval) — all store timer IDs in local variables or state instead of refs. A single utility hook `useStableTimer` would prevent recurrence.

3. **Unstable callback identity**: FE-70 (WS callbacks), FE-75 (stats callback), FE-76 (options object), FE-115/FE-116 (recommendation/statistics utilities) — all share the pattern of inline functions/objects in dependency arrays. A project-wide "ref-indirection for callbacks" convention would fix these systematically.

4. **Design system bypass**: FE-57 (themeConfig), FE-58 (AnalysisExportService), FE-85 (contrastChecker), FE-86 (theme.palette), FE-87 (breakpoints) — root cause is `themeConfig.ts` maintaining a parallel system. Fixing FE-57 first would reduce the delta for others.

5. **Accessibility keyboard gap**: FE-60 (DropZone), FE-95 (EnhancementIdentityLayer), FE-100 (TrackRow), FE-101 (checkbox) — the library view is almost entirely mouse-only. A single sweep adding `tabIndex`, `role`, `onKeyDown` to interactive elements would address all four.

## Prioritized Fix Order

1. **FE-100 + FE-60 + FE-95** — Keyboard navigation for track list and drop zone. Core accessibility gap.
2. **FE-55 + FE-56** — WebSocket type safety chain. Fixes propagate through all subscription hooks.
3. **FE-53** — EnhancementSection useCallback causing remounts. Quick fix, high UX impact.
4. **FE-54** — QueuePanel dragover API flood. Backend stability risk.
5. **FE-77** — Redux corruption from stale dispatch after unmount. Data integrity.
6. **FE-61 + FE-62** — Fix mock path and add fingerprint tests. Test reliability.
7. **FE-57** — Unify themeConfig with tokens. Root cause for design system drift.
8. **FE-99** — Increase `text.tertiary` contrast. WCAG compliance.
9. **FE-94** — Code splitting. Startup performance.
10. **FE-97** — Replace native `confirm()`. Consistency and accessibility.

---

*Report generated by Claude Opus 4.6 — 2026-03-20*
*Suggest next: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-03-20.md`*
