# Frontend Audit — 2026-03-22

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality, Redux State, Hook Correctness, TypeScript, Design System, API Client, Performance, Accessibility, Test Coverage
**Context**: Post-refactor audit. ~20 fixes landed since 2026-03-21 audit. Full deep re-audit of all 9 dimensions.

## Executive Summary

The refactor resolved **42 of 100 prior findings** (42% fix rate). This audit found **53 new findings** and confirmed **14 prior findings still open**. Two new HIGH-severity issues emerged from the refactor: `toggleShuffle` silently re-shuffles instead of unshuffling, and `setRepeatMode` calls a non-existent backend endpoint.

| Severity | New | Still Open | Fixed | Total Active |
|----------|-----|------------|-------|-------------|
| CRITICAL | 0 | 0 | 0 | 0 |
| HIGH | 4 | 1 | 3 | 5 |
| MEDIUM | 19 | 9 | 27 | 28 |
| LOW | 30 | 4 | 12 | 34 |
| **Total** | **53** | **14** | **42** | **67** |

**Key themes:**
1. **Broken queue operations (HIGH)** — Shuffle toggle and repeat mode are non-functional post-refactor
2. **Parallel state architectures persist** — `usePlaybackQueue` local state and `hooks/player/usePlaybackState` WS-driven state still duplicate Redux
3. **Accessibility progress** — 8 of 14 a11y findings fixed, but MediaCard grid remains mouse-only and new pane/sidebar buttons lack labels
4. **Type safety improving** — 12 of 17 `any` findings fixed, but `usePlayNormal` still has 4 `as any` casts and residual `payload?: any` in useRestAPI

## Prior Findings: Fix Verification

### Confirmed Fixed (42 issues)

| # | Description | Fix Commit |
|---|-------------|-----------|
| #2759 | 6 components decomposed | `10ea7b78` |
| #2814 | useWebSocketStatus derives from Redux | `c542f975` |
| #2960/#2975 | StreamingErrorBoundary real class boundary | `17c3aba6` |
| #2979 | PlayerControls uses Redux exclusively | `10ea7b78` |
| #2981 | StreamingErrorBoundary timer cleanup | `17c3aba6` |
| #2986 | similarityService /api prefix | `ecf1fe32` |
| #2989 | usePlaybackQueue snake_case handled | `7598019a` |
| #2987 | StandardizedAPIClient content-type guard | verified |
| #2991 | usePlayEnhanced polling gated on isPlaying | verified |
| #2992 | seek callback reads duration from ref | `2222ef9e` |
| #2993 | SelectableTrackRow wrapped in React.memo | `2cb2cfa3` |
| #2994 | useMasteringRecommendation 10s timeout | `ed75583e` |
| #2996 | AlbumCard/MediaCard wrapped in React.memo | verified |
| #2997 | useLibraryQuery deps fixed | `fde148dd` |
| #2999 | usePlayerStateSync typed | `13dd8f21` |
| #3001 | fetchPlayerStatus typed | `98d5fd1f` |
| #3002 | EnhancementInspectionLayer aria-labels | `b3d05d01` |
| #3003 | ConnectionStatusIndicator role | verified |
| #3004 | usePlaybackQueue typed guards | `c4aefe5c` |
| #3005 | PlayerControls preset aria | verified |
| #3008 | Dead mock removed | `26aebb43` |
| #3010 | Sleep assertions replaced with waitFor | verified |
| #3011 | processingService/AnalysisExportService tested | `4530ec6b` |
| #3012 | Six hooks tested | verified |
| #3014 | Dropdown outside-click dismiss | verified |
| #3016 | Duplicate formatTime centralized | verified |
| #3019 | QueueSearchPanel hooks before guard | verified |
| #3020 | WebSocketContext.subscribe typed | verified |
| #3021 | serializableCheck cleaned | verified |
| #3022 | Dead player_update subscription removed | verified |
| #3023 | errorTrackingMiddleware deferred dispatch | verified |
| #3024 | PlaybackResumedMessage added | `a0572b5d` |
| #3026 | MetadataUpdateRequest index sig | `03d28146` |
| #3028 | initialStreamingInfo spread copies | verified |
| #3029 | createMemoizedSelector typed | verified |
| #3031 | loggerMiddleware guard fixed | verified |
| #3033 | TrackGridView animation capped | verified |
| #3034 | makeSelectFilteredTracks typed | verified |
| #3036 | MediaCardArtwork uses img lazy | verified |
| #3038 | transformBackendTrack typed | verified |
| #3039 | usePlaybackControl duration from ref | verified |
| #3041 | useRestAPI T=unknown | verified |
| #3042 | console.debug guarded in usePlayEnhanced | verified |
| #3044 | errorTrackingMiddleware runtime guards | verified |
| #3045 | CozyAlbumGrid flatMap memoized | verified |
| #3047 | ApiError.details unknown | verified |
| #3048 | ArtworkMenuButton aria-label | verified |
| #3052 | TrackInfo alt text | verified |
| #3054 | NavigationSection aria-current | verified |
| #3056 | LoadingSpinner role=status | verified |
| #3059 | TrackCardOverlay label | verified |
| #3061 | loadMore toast on error | verified |
| #3063 | useLibraryStats AbortController | verified |
| #3064 | MSW timer cancelled | verified |
| #3065 | seek/setVolume response.ok | verified |
| #3067 | useSimilarTracks LRU cache | verified |
| #3068 | QUEUE_ADD positional index | verified |
| #3069 | refetchStats error exposed | verified |
| #3070 | useQueueTimeRemaining memoized | verified |

### Still Open (14 issues)

| # | Severity | Description |
|---|----------|-------------|
| #2962 | HIGH | usePlayNormal subscribes inside async callback — chunks dropped |
| #2976 | MEDIUM | handleClearTrack ignores trackId, clears all |
| #2977 | MEDIUM | Direct DOM style mutation — now 49 sites across 10 files |
| #2983 | MEDIUM | Dual queue state (Redux + usePlaybackQueue local) |
| #2985 | MEDIUM | useQueue selects entire slice |
| #2988 | MEDIUM | stop() only dispatches setIsPlaying(false) |
| #2998 | MEDIUM | TrackListViewContent inline arrow callbacks |
| #3000 | MEDIUM | MediaCard/AlbumCard no keyboard access |
| #3006 | MEDIUM | TrackTableRowItem MoreVert no aria-label |
| #3007 | MEDIUM | QueuePanel dialog no focus trap |
| #3009 | MEDIUM | usePlaybackControl.test.ts mock wrong shape |
| #3013 | MEDIUM | hooks/player/usePlaybackState no test |
| #2835 | LOW | QueuePanel role=option orphaned |
| #3062 | LOW | Enhancement test wrong import |

---

## New Findings

### HIGH (4)

---

### API-NEW-1: toggleShuffle never unshuffles — backend receives empty body
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts` (toggleShuffle)
- **Status**: NEW
- **Description**: `toggleShuffle` passes the `enabled` boolean as the third argument to `post()` (becomes a URL query param). The backend `shuffle_queue()` route has no parameters and always shuffles unconditionally. Disabling shuffle re-shuffles instead of restoring original order.
- **Impact**: Users cannot unshuffle their queue. Every toggle shuffles again.
- **Suggested Fix**: Backend needs an `unshuffle` endpoint or `shuffle` must accept a boolean body. Frontend must send `{ enabled }` as JSON body.

---

### API-NEW-2: setRepeatMode calls non-existent backend endpoint — always 404
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts` (setRepeatMode)
- **Status**: NEW
- **Description**: Calls `POST /api/player/queue/repeat` which does not exist in the backend router. Every invocation returns 404. Optimistic state is rolled back in catch, but repeat mode is completely non-functional.
- **Impact**: Repeat mode button does nothing. Users see momentary toggle then revert.
- **Suggested Fix**: Add `/api/player/queue/repeat` endpoint to backend, or change to the correct endpoint path.

---

### A11Y-N01: MediaCard grid entirely mouse-only — no keyboard access (extends #3000)
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCard.tsx`
- **Status**: NEW (extends still-open #3000 with additional detail)
- **Description**: No `tabIndex`, `role`, `onKeyDown`, or focus style. Play overlay only visible on hover. This is the primary content discovery surface.
- **Impact**: Keyboard and screen reader users cannot browse or play albums/tracks from grid view.
- **Suggested Fix**: Add `tabIndex={0}`, `role="button"`, `onKeyDown` for Enter/Space, focus-visible styling.

---

### A11Y-N02: QueuePanel ARIA ownership invalid — role=option without listbox parent (extends #2835)
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx`
- **Status**: NEW (extends still-open #2835 with severity upgrade)
- **Description**: Queue items have `role="option"` but parent `<ul>` has no `role="listbox"`. Invalid ARIA tree.
- **Impact**: Screen readers cannot enumerate queue items correctly.
- **Suggested Fix**: Add `role="listbox"` to parent `<ul>` or change items to `role="listitem"`.

---

### MEDIUM (19)

---

### CQ-NEW-1: StreamingErrorBoundary.handleDismiss untracked setTimeout
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `StreamingErrorBoundary.tsx:235`
- **Status**: NEW

### CQ-NEW-2: ComfortableApp keyboardShortcutsArray inline const with stale effect deps
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `ComfortableApp.tsx:279`
- **Status**: NEW

### CQ-NEW-5: CacheHealthMonitor double-poll (extends #2802)
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `CacheHealthMonitor.tsx:140`
- **Status**: NEW

### RDX-NEW-1: selectors.test.ts asserts initial volume === 70 but initialState is 80
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `store/selectors/__tests__/selectors.test.ts`
- **Status**: NEW

### RDX-NEW-2: CozyLibraryView shadow isPlaying/currentTrackId state + wrong WS message type
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `components/library/CozyLibraryView.tsx`
- **Status**: NEW

### DS-NEW-1: index.css imports Inter + Manrope overriding canonical Asap token
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `index.css`
- **Status**: NEW

### DS-NEW-2: 16 sites hardcode rgba(115,102,240,...) instead of tokens.colors.opacityScale.accent
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: Multiple files
- **Status**: NEW

### DS-NEW-3: 3 components still use deprecated rgba(102,126,234,...) (#667eea)
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `SimilarTracksHeader.tsx`, `SimilarTracksFooter.tsx`, `KeyboardShortcutsHeader.tsx`
- **Status**: NEW (escaped #2980 fix)

### DS-NEW-4: 12 files use hardcoded zIndex values instead of tokens.zIndex
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: Multiple components
- **Status**: NEW

### PERF-NEW-1: usePlayNormal console.debug in handleChunk unguarded in production
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `hooks/enhancement/usePlayNormal.ts:386`
- **Status**: NEW

### PERF-NEW-2: StarfieldBackground gl.getUniformLocation called 8-10x per rAF frame
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `components/background/StarfieldBackground.tsx:463-478`
- **Status**: NEW

### PERF-NEW-3: ProgressBar handleGlobalMouseMove recreated every 100ms during drag
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `components/player/ProgressBar.tsx:104-113`
- **Status**: NEW

### A11Y-N03–N05: Three pane/sidebar collapse/expand buttons missing aria-label
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: Expanded pane, Collapsed pane, CollapsedSidebar
- **Status**: NEW

### A11Y-N06: StreamingErrorBoundary missing role=alert/aria-live
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `StreamingErrorBoundary.tsx`
- **Status**: NEW

### A11Y-N07: QueueManager drag-only reorder with no keyboard alternative
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `QueueManager.tsx`
- **Status**: NEW

### A11Y-N08: PlaybackControls buttons use title only, no aria-label
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `PlaybackControls.tsx`
- **Status**: NEW

### A11Y-N09: SearchResultItem role=button div has no accessible name
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `QueueSearchPanel.tsx`
- **Status**: NEW

### TC-1: setup.ts global WS mock includes phantom sendMessage field
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `test/setup.ts`
- **Status**: NEW (root cause of #3009)

### TC-2: Six library/shared hooks untested (449 lines)
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `useAlbumsQuery`, `useArtworkUpdates`, `useInfiniteAlbums`, `useLibraryStats`, `useRecentlyTouched`, `useStandardizedAPI`
- **Status**: NEW

---

### LOW (30)

Key LOW clusters:

**Component Quality (2)**: Player lacks dedicated ErrorBoundary (CQ-NEW-3), QueueStatisticsPanel index keys (CQ-NEW-4)

**Redux State (6)**: stop() missing dispatch dep (RDX-NEW-3), cacheSlice naming inconsistency (RDX-NEW-4), duplicate selector exports (RDX-NEW-5), usePlayerState/useConnectionState select entire slices (RDX-NEW-6), usePlaybackQueue stale lastUpdated (RDX-NEW-7), hooks/player/usePlaybackState parallel WS state (RDX-NEW-8)

**Hook Correctness (7)**: useEnhancementControl get dep risk (HC-NEW-1), AudioContext never closed (HC-NEW-2), useQueueRecommendations unstable functions (HC-NEW-3), handleScanFolder missing dep (HC-NEW-4), usePlayerStreaming drift timer (HC-NEW-5), usePaginatedAPI reset unstable (HC-NEW-6), usePaginatedAPI timeout dep fragile (HC-NEW-7)

**Type Safety (11)**: usePlayEnhanced data as any (TS-NEW-1), handleFingerprintProgress any (TS-NEW-2), useRestAPI payload any (TS-NEW-3), usePlaybackQueue message as any (TS-NEW-4), TrackedError.context any (TS-NEW-5), useReduxState setStats any (TS-NEW-6), ApiErrorHandler.parse any (TS-NEW-7), useLibraryQuery album/artist any (TS-NEW-8), settings onSettingChange value any (TS-NEW-9), log data any (TS-NEW-10), QueueRecommendations onAddTrack any (TS-NEW-11)

**Design System (5)**: Breakpoint mismatch (DS-NEW-5), theme.palette usage (DS-NEW-6), deep token imports (DS-NEW-7), theme-color meta black (DS-NEW-8), MUI direct imports (DS-NEW-9)

**Performance (3)**: QueuePanel inline callbacks (PERF-NEW-4), CozyAlbumGrid/EraSection inline callbacks (PERF-NEW-5), Player handlers not useCallback (PERF-NEW-6)

**Accessibility (4)**: TrackList role mismatch (A11Y-N10), ConnectionStatusIndicator panel (A11Y-N11), AlbumActionButtons labels (A11Y-N12), ClearQueueDialog escape/heading (A11Y-N13)

**Test Coverage (3)**: useQueueHistory type-only test (TC-3), libraryService/keyboardShortcutsService untested (TC-4), setup.ts setTimeout hacks (TC-5)

**API Client (1)**: useLibraryWithStats.refetchStats no AbortController (API-NEW-3)

---

## Relationships & Shared Root Causes

1. **Parallel state architectures** (6 findings): `usePlaybackQueue` local state (#2983), `hooks/player/usePlaybackState` WS-driven state (RDX-NEW-8), `CozyLibraryView` shadow state (RDX-NEW-2), `usePlaybackQueue.state.lastUpdated` (RDX-NEW-7) — all bypass Redux, causing divergence.

2. **Broken queue control** (2 HIGH findings): API-NEW-1 (shuffle) and API-NEW-2 (repeat) are both symptoms of incomplete backend API coverage for queue operations.

3. **Inline callback instability** (4 findings): #2998, PERF-NEW-4, PERF-NEW-5, PERF-NEW-6 — all pass inline arrows to memoized children in list rendering contexts.

4. **Residual `any` after partial fixes** (6 findings): TS-NEW-1 through TS-NEW-6 are leftover `any` parameters in files where the primary `any` issue was fixed but secondary sites were missed.

5. **Accessibility button labels** (5 findings): A11Y-N03–N05, N08, N12 — all icon-only buttons missing `aria-label`. Same pattern, same fix.

## Prioritized Fix Order

1. **API-NEW-1 + API-NEW-2** — Broken shuffle/repeat. Non-functional features visible to every user.
2. **#2962** — usePlayNormal audio chunk race. Silent playback failure.
3. **A11Y-N01 + #3000** — MediaCard keyboard access. Primary content surface inaccessible.
4. **A11Y-N02 + #2835** — QueuePanel ARIA ownership. Invalid accessibility tree.
5. **PERF-NEW-3** — ProgressBar drag handler recreation. Active UX degradation during seek.
6. **#2983 + RDX-NEW-2 + RDX-NEW-8** — Parallel state consolidation. Root cause for multiple state divergence bugs.
7. **RDX-NEW-1** — Broken test assertion. CI may be silently failing.
8. **DS-NEW-1** — Font override. Two unnecessary font downloads per page load.
9. **TC-1** — setup.ts phantom field. Root cause for #3009 mock mismatch.
10. **PERF-NEW-2** — WebGL uniform location caching. ~600 unnecessary driver calls/sec.

---

*Report generated by Claude Opus 4.6 — 2026-03-22*
*Suggest next: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-03-22.md`*
