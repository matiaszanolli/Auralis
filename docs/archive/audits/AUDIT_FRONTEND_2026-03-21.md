# Frontend Audit — 2026-03-21

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality, Redux State, Hook Correctness, TypeScript, Design System, API Client, Performance, Accessibility, Test Coverage
**Method**: 9 parallel dimension agents (Sonnet), followed by manual merge, deduplication, and cross-dimension analysis.

## Executive Summary

This audit reveals **5 HIGH**, **38 MEDIUM**, and **55 LOW** findings across all 9 dimensions. No CRITICAL findings were confirmed. All findings are NEW (not duplicates of existing open issues).

**Most impactful clusters:**

1. **Type erosion via `any` (22 findings)** — WebSocket subscriptions, API responses, Redux middleware, and service layers use `any` parameters that defeat TypeScript's discriminated union narrowing. The chain starts at `WebSocketContext.subscribe(messageType: string)` (FE-90) and propagates through every WS hook that casts `message as any`.

2. **Hook correctness (13 findings)** — `usePlayNormal` subscribes inside an async callback creating a race window where audio chunks are dropped (FE-120, HIGH). Five other hooks have stale closures, uncancelled timers, or missing deps causing cascading re-renders.

3. **Accessibility gaps (12 findings)** — `MediaCard`/`AlbumCard` (the primary content surface) has no keyboard access (FE-133). Enhancement preset selection is fully mouse-only (FE-134, HIGH). Six icon buttons lack `aria-label`.

4. **Design system drift (15 findings)** — `index.css` global glow variables use wrong purple `#7C3AED` vs token `#7366F0` (FE-124, HIGH). 17+ `rgba(0,0,0,…)` pure-black usages violate the "no pure black" design rule (FE-128, HIGH).

5. **Test coverage gaps (9 findings)** — `usePlaybackState` (5 exported hooks, 8-event WS state machine) has zero tests (FE-136, HIGH). `useMasteringRecommendation` mock has wrong shape (FE-137, HIGH). Two large services (1,300 combined lines) untested.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 38 |
| LOW | 55 |
| **Total** | **98** |

---

## New Findings

### HIGH

---

### FE-136: Five player hooks entirely untested — false confidence from naming coincidence
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts`
- **Status**: NEW
- **Description**: `usePlaybackState`, `usePlaybackPosition`, `useCurrentTrack`, `useIsPlaying`, and `useVolume` — the lowest layer of the player state machine with 8 WS event subscriptions — have zero unit tests. A same-named hook at `components/library/usePlaybackState.ts` *is* tested, creating false confidence.
- **Evidence**: `usePlaybackControl.test.ts` mocks the player-layer hook away rather than testing it. No test exercises the 8-event state machine, position resets, or default volume (80).
- **Impact**: Regressions in the core player state machine are invisible.
- **Suggested Fix**: Add `renderHook` tests for all 5 hooks covering message type routing, state transitions, and defaults.

---

### FE-137: `useMasteringRecommendation` untested; integration mock has wrong shape
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useMasteringRecommendation.ts`
- **Status**: NEW
- **Description**: No unit test. The only integration mock returns `{ recommendation, isLoading, error }` but the real hook returns `{ recommendation, isLoading, clearRecommendation, isHybrid }`. Mock adds spurious `error` field and omits `clearRecommendation` and `isHybrid`.
- **Impact**: Components calling `clearRecommendation()` or reading `isHybrid` are silently untested.
- **Suggested Fix**: Add unit tests; fix mock shape in integration test.

---

### FE-120: `usePlayNormal` subscribes inside async callback — audio chunks dropped during fetch
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:432-508`
- **Status**: NEW
- **Description**: `playNormal` calls `cleanupStreaming()` (unsubscribes all WS listeners), then `await fetch()` for track data, then re-subscribes. During the async fetch window, `audio_stream_start`/`audio_chunk` messages are silently dropped — no listener exists. `usePlayEnhanced` correctly subscribes once on mount.
- **Impact**: Silent playback failure — buffer never fills, engine never starts.
- **Suggested Fix**: Mirror `usePlayEnhanced`: subscribe once in a mount `useEffect`, use stable callback refs.

---

### FE-134: Enhancement preset selector entirely mouse-only
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/enhancement/EnhancementInspectionLayer.tsx:283-337`
- **Status**: NEW
- **Description**: Preset dropdown trigger missing `aria-expanded`/`aria-haspopup`. Menu items are plain `<div>`s with no `role`, `tabIndex`, or `onKeyDown`. Intensity slider has no `aria-label`.
- **Impact**: Entire enhancement preset selection workflow is mouse-only.
- **Suggested Fix**: Add `aria-haspopup="listbox"`, `aria-expanded`, `role="option"` items, keyboard Escape dismiss.

---

### FE-124: Global CSS glow variables use wrong purple — `#7C3AED` vs token `#7366F0`
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/index.css` (8 locations: `--glow-subtle/medium/strong`)
- **Status**: NEW
- **Description**: Global CSS variables `--glow-subtle`, `--glow-medium`, `--glow-strong` use `rgba(124, 58, 237, …)` (`#7C3AED`) — a different purple from the canonical token `#7366F0`. Applied to scrollbars, focus rings, and aurora background elements globally.
- **Impact**: Visual inconsistency across all scrollbar and focus ring styling.
- **Suggested Fix**: Replace with `tokens.colors.accent.primary` equivalent.

---

### MEDIUM

---

### CQ-1: StreamingErrorBoundary is not a real React error boundary
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/enhancement/StreamingErrorBoundary.tsx:164-352`
- **Status**: NEW
- **Description**: Named `StreamingErrorBoundary` but is a function component accepting an `error: string | null` prop. No `getDerivedStateFromError`/`componentDidCatch`. Cannot catch rendering exceptions in streaming subtrees.
- **Impact**: Runtime rendering errors crash the entire app instead of showing localized recovery UI.
- **Suggested Fix**: Rename to `StreamingErrorDisplay`. Optionally add a real class-based error boundary.

---

### CQ-3: `handleClearTrack` ignores `trackId` argument, silently clears ALL cache
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/CacheManagementPanel.tsx:297-309`
- **Status**: NEW
- **Description**: `handleClearTrack(_trackId)` ignores its argument and calls `clearCache()` (all cache). The confirmation dialog tells the user only the selected track will be cleared.
- **Impact**: Users unknowingly delete entire cache including tracks being streamed.
- **Suggested Fix**: Implement per-track clear endpoint, or disable the per-track button with tooltip.

---

### CQ-4: Direct DOM style mutation via `e.target as HTMLButtonElement` (45 sites)
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `PlayerControls.tsx`, `QueueManager.tsx`, `CacheManagementPanel.tsx` (5 files, 45 occurrences)
- **Status**: NEW
- **Description**: `onMouseOver`/`onMouseOut` handlers directly mutate `e.target.style.*`, bypassing React reconciliation.
- **Impact**: Visual glitches after React re-renders; no hover equivalent for keyboard focus.
- **Suggested Fix**: Replace with CSS `:hover` via MUI `sx` prop.

---

### CQ-8: CacheStatsDashboard/CacheHealthMonitor intervals survive rendering crashes
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `CacheStatsDashboard.tsx:191-197`, `CacheHealthMonitor.tsx:140-146`
- **Status**: NEW
- **Description**: `setInterval` auto-refresh loops with no wrapping error boundary. After a rendering crash, the interval continues polling in the background.
- **Suggested Fix**: Wrap in `<ErrorBoundary>`.

---

### CQ-11: `PlayerControls` (535 lines) is a parallel player duplicating Redux-backed `Player`
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/PlayerControls.tsx:1-535`
- **Status**: NEW
- **Description**: Maintains its own local `playerState` via separate WebSocket subscription, entirely duplicating the canonical `Player` component using Redux. Two state machines drift out of sync.
- **Suggested Fix**: Remove and replace with Redux-backed `Player` component.

---

### CQ-2: Uncleared setTimeout in StreamingErrorBoundary.handleRetry
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `StreamingErrorBoundary.tsx:207-211`
- **Status**: NEW
- **Description**: Backoff `setTimeout` not stored in ref, not cancelled on unmount. `onRetry()` fires on stale/unmounted state.
- **Suggested Fix**: Store timeout ID in `useRef`, cancel in cleanup.

---

### CQ-10: EnhancementInspectionLayer custom dropdown lacks a11y and outside-click dismiss
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `EnhancementInspectionLayer.tsx:282-328`
- **Status**: NEW
- **Description**: No `aria-expanded`, `aria-haspopup`, `role="listbox"`, keyboard Escape, or outside-click dismiss.
- **Suggested Fix**: Add proper ARIA attributes and keyboard handlers.

---

### FE-R120: Dual parallel queue state diverges silently
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `usePlaybackQueue.ts`, `queueSlice.ts`, `QueuePanel.tsx`
- **Status**: NEW
- **Description**: Redux `queueSlice` and `usePlaybackQueue` local React state exist simultaneously. `shuffle` and `repeatMode` are invisible to Redux entirely.
- **Impact**: Users see stale queue contents in some views.
- **Suggested Fix**: Promote `shuffle`/`repeatMode` into `queueSlice`. Replace local state with `useSelector`.

---

### FE-R121: `useQueue` subscribes to entire queue slice
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `useReduxState.ts:133`
- **Status**: NEW
- **Description**: Selects entire `state.queue` object. Every queue action re-renders all consumers. `usePlayer` was fixed (#2537) but `useQueue` was not.
- **Suggested Fix**: Split into granular per-field selectors.

---

### FE-R122: `stop()` dispatches only `setIsPlaying(false)` — Redux diverges from `playback_stopped`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `usePlaybackControl.ts:181-205`
- **Status**: NEW
- **Description**: Between `stop()` and the WS broadcast, Redux shows stale track/queue data.
- **Suggested Fix**: Also dispatch `setCurrentTrack(null)` and `clearQueue()`.

---

### FE-H121: `toggleEnabled` stale closure with WS race
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `useEnhancementControl.ts:184-212`
- **Status**: NEW
- **Description**: WS `enhancement_settings_changed` during in-flight POST causes optimistic update to overwrite correct server state.
- **Suggested Fix**: Use functional state updater `setState(prev => ({ ...prev, enabled: !prev.enabled }))`.

---

### FE-H123: `seek` dep on `playbackState.duration` causes recreation on every WS broadcast
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `usePlaybackControl.ts:213-233`
- **Status**: NEW
- **Description**: `seek` recreated on every `player_state` message (~1Hz). Cascading re-renders in all consumers.
- **Suggested Fix**: Read duration from ref at call time, remove from dep array.

---

### FE-H124: `useMasteringRecommendation` isLoading never resets if WS message never arrives
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `useMasteringRecommendation.ts:44-69`
- **Status**: NEW
- **Description**: No timeout, no error path, no cleanup to reset `isLoading`. Permanent spinner if backend never sends message.
- **Suggested Fix**: Add 10s timeout fallback.

---

### FE-H125: `useLibraryStats.fetchStats` not wrapped in `useCallback`, no unmount guard
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `useLibraryStats.ts:16-36`
- **Status**: NEW

---

### FE-H126: `useLibraryQuery` auto-fetch effect omits `limit`/`endpoint` from deps
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `useLibraryQuery.ts:338-347`
- **Status**: NEW
- **Description**: `eslint-disable` hides missing deps. Changing page size or endpoint silently has no effect.

---

### FE-T84: `usePlayerStateSync` subscribes via `message: any`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `usePlayerStateSync.ts:53`
- **Status**: NEW
- **Description**: WS callback parameter is `any`, discarding `PlayerStateMessage`/`RawPlayerStateData` types. Backend shape changes produce silent `undefined` at runtime.

---

### FE-T85: `usePlayerAPI.fetchPlayerStatus` assigns untyped `response.json()` to typed state
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `usePlayerAPI.ts:83-93`
- **Status**: NEW

---

### FE-T86: `usePlaybackQueue` casts WS message `as any`, defeating discriminated union
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `usePlaybackQueue.ts:176`
- **Status**: NEW

---

### FE-T87: `useMasteringRecommendation` handler typed `any` instead of typed WS message
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `useMasteringRecommendation.ts:53-55`
- **Status**: NEW

---

### FE-125: Deprecated `rgba(102,126,234)` (`#667eea`) still in 3 components
- **Severity**: MEDIUM (reclassified from design system HIGH for consistency with prior audit)
- **Dimension**: Design System
- **Location**: `KeyboardShortcutsHeader.tsx`, `SimilarTracksHeader.tsx`, `SimilarTracksFooter.tsx`
- **Status**: NEW

---

### FE-126: `CacheHealthMonitor` uses undocumented teal `#00D4AA`
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `CacheHealthMonitor.tsx`
- **Status**: NEW

---

### FE-127: `ShuffleModeSelector.module.css` introduces `--accent-dark: #5A5CC4`
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `ShuffleModeSelector.module.css`
- **Status**: NEW

---

### FE-128: 17+ `rgba(0,0,0,…)` pure-black usages in 11 components
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `MediaCardOverlay`, `CacheManagementPanel`, `QueuePanel`, `AdvancedSettingsPanel`, `Player`, `TrackCardStyles`, and others
- **Status**: NEW
- **Description**: Violate the "no pure black" design rule (base is `#0B1020` deep blue-black). Token `colors.opacityScale.dark.*` exists for this purpose.

---

### FE-DS129-135: Additional design system drift (7 findings)
- **Severity**: MEDIUM
- **Locations**: `ArtistList.styles.ts`, `Grid.styles.ts`, `Tabs.styles.ts`, `AppTopBar.styles.ts`, `EnhancementToggleStyles.ts`, `ArtistTrackRow.tsx` (11 sites using `color: 'text.secondary'` MUI shortcut), `5 files using fontSize: '0.7rem'`
- **Status**: All NEW
- **Description**: Mix of raw spacing values, `theme.palette` usage, off-token navy rgba values, MUI string color shortcuts bypassing tokens, and non-token font sizes.

---

### FE-D6-08: `similarityService.ts` missing `/api` prefix — all endpoints 404
- **Severity**: MEDIUM (reclassified from agent HIGH — service is effectively dead code, not blocking production)
- **Dimension**: API Client
- **Location**: `services/similarityService.ts:19`
- **Status**: NEW
- **Description**: `API_BASE = '/similarity'` instead of `'/api/similarity'`. All 6 public functions return 404. `useSimilarTracks` builds URLs correctly independently.

---

### FE-D6-01: `useRestAPI` stale-response check fires after body consumed
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/api/useRestAPI.ts:112-116`
- **Status**: NEW

---

### FE-D6-04: `useLibraryWithStats.loadMore` setTimeout(0) anti-pattern (second instance)
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/library/useLibraryWithStats.ts:228-235`
- **Status**: NEW

---

### FE-D6-06: `StandardizedAPIClient` retries non-JSON 502/503 error responses
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `services/api/standardizedAPIClient.ts:272-304`
- **Status**: NEW

---

### FE-D6-11: `usePlaybackQueue` initial fetch expects camelCase, backend returns snake_case
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/player/usePlaybackQueue.ts:218-224`
- **Status**: NEW
- **Description**: `currentIndex`, `isShuffled`, `repeatMode` always fall back to defaults.

---

### Performance: 4 MEDIUM findings
- **FE-P1**: `usePlayEnhanced` 100ms polling runs unconditionally — 10 re-renders/sec when idle (`usePlayEnhanced.ts:838-845`)
- **FE-P2**: `SelectableTrackRow` not wrapped in `React.memo` — negates inner `TrackRow` memo
- **FE-P3**: `AlbumCard`/`MediaCard` not memoized — 50+ cards re-render on any parent state change
- **FE-P4**: `TrackListViewContent` inline arrow callbacks defeat memoization
- **Status**: All NEW

---

### Accessibility: 6 MEDIUM findings
- **FE-133**: MediaCard/AlbumCard/TrackCard no keyboard access (entire grid view mouse-only)
- **FE-135**: EnhancementInspectionLayer control buttons missing `aria-label`
- **FE-136**: ConnectionStatusIndicator clickable div missing role/keyboard
- **FE-137**: PlayerControls preset buttons no `aria-label`/`aria-pressed`
- **FE-138**: TrackTableRowItem MoreVert button missing `aria-label`, row not keyboard-focusable
- **FE-141**: QueuePanel dialog has no focus trap
- **Status**: All NEW

---

### Test Coverage: 4 MEDIUM findings
- **FE-138**: Dead mock targeting non-existent module in `usePlaybackState.test.ts`
- **FE-139**: `usePlaybackControl.test.ts` mock has wrong shape (missing fields, invented fields)
- **FE-140**: Sleep-based assertions (3 instances) in WebSocket realtime integration test
- **FE-141**: `processingService.ts` (373 lines) and `AnalysisExportService.ts` (934 lines) have zero tests
- **FE-142**: Six hooks with no unit tests (`useWebSocketErrors`, `useGroupedArtists`, etc.)
- **Status**: All NEW

---

### LOW

55 LOW findings across all dimensions. Key clusters:

**Component Quality (4)**: Duplicate `formatTime` implementations (11 copies), index keys in reorderable lists (2 files), `QueueSearchPanel` hook after early return.

**Redux State (6)**: Spurious `serializableCheck` suppressions, re-entrant dispatch in error middleware, `Object.assign` with `undefined` partials, shared `initialStreamingInfo` reference, logger `isDispatching` guard swallows recovery dispatches, untyped `makeSelectFilteredTracks` predicate.

**Hook Correctness (7)**: `useQueueHistory.undo` dep churn, `useOptimisticUpdate.reset` inline object instability, `useStaggerAnimation.setRef` not memoized, `useSynchronizedVisualizations` rAF restart on render, `useAppLayout` stale toggles, `useLibraryData` toast dep risk, `useRestAPI` shared sequence counter.

**Type Safety (14)**: `RawPlayerStateData` loose `string` types (2), `subscribe` accepts `string` not `WebSocketMessageType`, dead `player_update` subscription, missing `PlaybackResumedMessage` type, `MetadataUpdateRequest` index signature, `createMemoizedSelector` loses types, `makeSelectFilteredTracks` predicate `any`, `usePlayEnhanced` wrappers `any`, type guards accept `any` not `unknown`, `transformBackendTrack` accepts `Record<string, any>`, `useRestAPI` defaults `T = any`, middleware casts action to `Record<string, any>`, `ApiError.details` is `Record<string, any>`.

**Design System (3)**: `var(--silver)` CSS variable, `AdvancedSettingsPanel` hardcoded dialog styles, `index.css` `@media` 768px vs token 900px.

**API Client (7)**: `loadMore` errors not surfaced, `useLibraryStats` no abort, `usePlayerAPI` seek/volume swallow errors, module-level similarity cache unbounded, `cancelJob` retry risk, `refetchStats` swallows errors, `useLibraryQuery` missing `limit` dep.

**Performance (6)**: Staggered animation delay O(n) style recalc, `MediaCardArtwork` CSS background (no lazy), `usePlaybackControl` full WS subscription for one field, `console.debug` in hot chunk path, `setTimeout(0)` state read, `CozyAlbumGrid` unstable array reference.

**Accessibility (5)**: `ArtworkMenuButton` missing label, `TrackInfo` alt text, `NavigationSection` no `aria-current`, `LoadingSpinner` no status role, `TrackCardOverlay` play button missing label.

**Test Coverage (2)**: Enhancement integration test bypasses `test-utils`, network timeout test leaves dangling 10s timer.

---

## Relationships & Shared Root Causes

1. **`any` propagation chain** (22 findings): `WebSocketContext.subscribe(string)` (FE-90) → hooks cast `message as any` (FE-T84, FE-T86, FE-T87, FE-96) → Redux middleware accepts `any` → `useRestAPI<T = any>` → consumers receive untyped data. Fixing FE-90 to accept `WebSocketMessageType` and changing `T = any` defaults to `T = unknown` would tighten the entire chain.

2. **Dual state architecture** (4 findings): `usePlaybackQueue` local state (FE-R120), `PlayerControls` local state (CQ-11), `usePlaybackState` WS-driven state all duplicate Redux. Root cause: Redux was added after the WS-driven hooks, and the hooks were never migrated.

3. **Stale closure / ref-vs-state** (7 findings): FE-H121 (toggleEnabled), FE-H123 (seek duration), FE-H124 (mastering loading), FE-H125 (fetchStats), CQ-2 (retry timer), FE-131 (layout toggles), FE-132 (toast deps) — all store values in closures instead of refs.

4. **Inline callback instability** (5 findings): FE-P4 (TrackListViewContent), FE-P3 (AlbumCard), FE-P2 (SelectableTrackRow), FE-H123 (seek dep), FE-130 (rAF restart) — missing `React.memo` + `useCallback` at list rendering boundaries.

5. **Design system escape hatches** (15 findings): Root cause is three parallel color systems: `tokens.ts`, `themeConfig.ts`, and `index.css` CSS variables. Unifying to a single source (tokens) would eliminate 12 of the 15 findings.

## Prioritized Fix Order

1. **FE-120** — `usePlayNormal` dropped audio chunks. Critical UX impact, quick fix (mirror `usePlayEnhanced` pattern).
2. **FE-R120 + CQ-11** — Dual queue state and parallel `PlayerControls`. Root cause for state divergence across the entire app.
3. **FE-T84 + FE-90** — Type `subscribe` parameter and WS handler callbacks. Enables TypeScript to catch backend contract changes.
4. **FE-133 + FE-134** — Keyboard access for MediaCard grid and enhancement presets. Core a11y gap.
5. **FE-136 + FE-137** — Add player hook and mastering recommendation tests. Fix mock shapes.
6. **FE-P1** — Unconditional 100ms polling. Quick fix (`prev !== time` guard), large perf impact.
7. **FE-P2 + FE-P3 + FE-P4** — Memoize list rendering chain. Eliminates 50+ unnecessary re-renders on state changes.
8. **FE-124 + FE-128** — Global CSS color corrections. Visual consistency.
9. **FE-D6-11** — Snake_case conversion for queue initial fetch. Data correctness.
10. **FE-H124** — Mastering recommendation timeout. Prevents permanent spinners.

---

*Report generated by Claude Opus 4.6 — 2026-03-21*
*Suggest next: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-03-21.md`*
