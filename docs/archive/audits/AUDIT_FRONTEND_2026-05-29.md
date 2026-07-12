# Frontend Audit — 2026-05-29

**Scope**: `auralis-web/frontend/src/` — React 18 + TypeScript + Vite + Redux + MUI
**Depth**: deep (full call-graph tracing)
**Methodology**: 9 dimension agents (Component Quality, Redux State, Hook Correctness, Type Safety, Design System, API Client, Performance, Accessibility, Test Coverage). Findings verified against current code; deduplicated against `gh issue list` (140 open issues) and prior `AUDIT_FRONTEND_2026-05-26.md`.

**Dedup baseline**: All 82 findings from the 2026-05-26 audit were verified. Most are fixed; surviving open issues are cross-referenced but NOT re-filed. This report documents only NEW findings and regressions of closed issues.

---

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 1 |
| HIGH | 12 |
| MEDIUM | 30 |
| LOW | 36 |
| **Total NEW findings** | **79** |
| Existing cross-refs (not re-filed) | 3 |

### Per-dimension breakdown

| # | Dimension | CRIT | HIGH | MED | LOW | Total |
|---|-----------|------|------|-----|-----|-------|
| 1 | Component Quality | 1 | 0 | 4 | 2 | 7 |
| 2 | Redux State | 0 | 0 | 2 | 3 | 5 |
| 3 | Hook Correctness | 0 | 1 | 4 | 7 | 12 |
| 4 | Type Safety | 0 | 1 | 3 | 4 | 8 |
| 5 | Design System | 0 | 1 | 4 | 7 | 12 |
| 6 | API Client | 0 | 0 | 3 | 3 | 6 |
| 7 | Performance | 0 | 2 | 4 | 2 | 8 |
| 8 | Accessibility | 0 | 4 | 5 | 2 | 11 |
| 9 | Test Coverage | 0 | 3 | 4 | 3 | 10 |
| | **TOTAL** | **1** | **12** | **29** | **33** | **79** |

### Key themes

1. **React Rules of Hooks violation (CRITICAL)** — `LibraryViewRouter` calls 9 hooks inside an `if (view === 'albums')` branch with deliberate `eslint-disable` suppressions. This corrupts React's hook fiber on every `albums ↔ artists` transition (CQ-1).
2. **Redux `currentTime` never updates during playback** — `position_changed` WS messages sent by the backend at 1 Hz are silently ignored by the frontend (no subscriber). `selectCurrentTime`, `selectFormattedTime`, and `usePlaybackProgress` serve frozen values between state-change events (RS-5).
3. **Test suite has three HIGH-severity failures that mask real bugs** — `usePlayNormal` (~18 tests) crashes on every mount due to a missing mock field (TC-1); `queueSlice` repeat-mode reducer branches are completely untested (TC-2); the "streaming integration" test suite exercises a self-contained test fixture, not production code (TC-3).
4. **Accessibility gaps in interactive controls** — `MetadataEditorDialog` has no `role="dialog"`, focus trap, or label association (A11Y-1); recommendation-panel add-buttons are hover-only and unreachable by keyboard (A11Y-7); `ArtistTrackRow` interactive rows have no keyboard activation (A11Y-6); `CozyAlbumGrid` has a broken ARIA grid hierarchy (A11Y-8).
5. **Performance: two `React.memo` busts in the hot render path** — `TrackGridView` grid path has no virtualizer AND inline `sx` objects defeat `TrackCard.memo` (PF-1); `CozyAlbumGrid` inline `onHoverEnter` creates new function refs on every virtualizer tick (PF-2).
6. **`apiRequest.ts` HTTP helpers default to `T = any`** — every call site that omits the type parameter silently gets `any`, making backend schema changes invisible to TypeScript (TS-1).
7. **Design system drift: `index.css` CSS variables out of sync** — border-radius, color, and transition values in `index.css` diverge from `tokens` on three dimensions, affecting default body text color and all custom elements using CSS vars (DS-1).
8. **`useEnhancementControl` fires 3 redundant API requests on app load** — three simultaneously-mounted callers each fetch `/api/player/enhancement/status` independently with no shared cache (PF-4).
9. **`usePlaybackQueue` initial fetch has no AbortController** — stale responses can overwrite freshly-mounted Redux queue state; same pattern in `useQueueHistory` and `useEnhancementControl` (HC-2).
10. **`CacheManagementPanel` and `usePlaybackState` bypass `useStandardizedAPI`** — one calls `fetch()` directly without unmount guard; the other ignores `response.ok` before proceeding with playback (CQ-5, AC-3).

### Most impactful (priority single-PR fixes)

1. **CQ-1** — Extract `AlbumsView` sub-component; single file change eliminates the CRITICAL hook violation.
2. **RS-5** — Add one `subscribe('position_changed', ...)` call in `usePlayerStateSync`; fixes frozen Redux position counter.
3. **TC-1** — Add `setResumePositionGetter: vi.fn()` to the mock; unlocks 18 dead normal-playback tests.
4. **TC-4** — Two `true → false` changes in `setup.ts` breakpoint mock; fixes all tests running in wrong viewport.
5. **TS-1** — Change 6 `T = any` defaults to `T = unknown` in `apiRequest.ts`; enforces type safety on all HTTP callers.
6. **A11Y-1** — Apply `useDialogAccessibility` hook to `MetadataEditorDialog` (already used by `ClearQueueDialog`).
7. **AC-3** — Add `if (!response.ok) throw` in `usePlaybackState.handlePlayTrack`; stops silent playback-on-failed-queue.
8. **PF-1** — Apply existing `useGridVirtualizer` to `TrackGridView`; hoist animation `sx` to stable constant array.
9. **TC-2** — Add 4 test cases to `queueSlice.test.ts`; covers all `repeatMode` branches.
10. **DS-1** — Align `index.css` CSS vars with `tokens.borderRadius`, `tokens.colors`, `tokens.transitions`.

---

## Findings

### CRITICAL

---

### CQ-1: `LibraryViewRouter` calls 9 hooks inside conditional branches — Rules of Hooks violation
- **Severity**: CRITICAL
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:93-136`
- **Status**: NEW
- **Description**: Nine hooks (`useState` ×4, `useCallback` ×3, `useAlbumFingerprint`, `useRecentlyTouched`) are called inside `if (view === 'albums')` with deliberate `// eslint-disable-next-line react-hooks/rules-of-hooks` suppressions at each site. When `view` transitions between `albums` and `artists`, React's hook fiber order changes, corrupting state slot assignments and producing stale closures, wrong fingerprint data for the displayed album, or an `InvalidHookCallError` crash that propagates past the library `ErrorBoundary`.
- **Evidence**:
  ```tsx
  if (view === 'albums') {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [hoveredAlbumId, setHoveredAlbumId] = useState<number | null>(null);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { fingerprint } = useAlbumFingerprint(hoveredAlbumId ?? 0, ...);
    // ... 7 more hooks inside the conditional
  }
  ```
- **Impact**: Switching between Albums and Artists views silently corrupts React's internal fiber. Users see stale hover state or wrong fingerprint data; on repeated rapid switching a React invariant violation may crash the library subtree entirely.
- **Suggested Fix**: Extract `AlbumsView` and `ArtistsView` as sibling sub-components. Each holds its own state unconditionally. `LibraryViewRouter` becomes a pure switch with no hooks of its own.

---

### HIGH

---

### HC-2: `usePlaybackQueue` initial-fetch effect has no AbortController — stale data dispatched on remount
- **Severity**: HIGH
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:241-266`
- **Status**: NEW
- **Description**: The `fetchInitialQueue` async function inside `useEffect` calls `get('/api/player/queue')` with no cleanup and no abort signal. If the component unmounts between request resolution and the `dispatch()` calls, stale queue data is pushed into Redux. In React 18 Strict Mode, the double-invoke sends two simultaneous requests; both responses are applied in arrival order, which may be reversed.
- **Evidence**:
  ```typescript
  useEffect(() => {
    const fetchInitialQueue = async () => {
      const response = await get<Record<string, unknown>>('/api/player/queue');
      if (response) {
        dispatch(reduxSetQueue(...));      // no isActive guard
        dispatch(reduxSetCurrentIndex(...)); // no isActive guard
      }
    };
    fetchInitialQueue();
  }, [get, dispatch]);  // no cleanup return
  ```
- **Impact**: Stale queue data may transiently overwrite a fresh queue set by navigation or `play_enhanced`. In Strict Mode, duplicate dispatches fire on every mount.
- **Siblings**: `useQueueHistory` (line 153–171, no abort on `fetchInitialHistory`); `useEnhancementControl` (line 171–191, no abort on `fetchInitialState`).
- **Suggested Fix**: Add `let isActive = true; return () => { isActive = false; }` and gate all dispatches on `if (isActive)`.

---

### TS-1: `apiRequest.ts` HTTP helpers default to `T = any` — all untyped callers silently receive `any`
- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:56,119,127,139,151,163`
- **Status**: NEW
- **Description**: All six HTTP helpers (`apiRequest`, `get`, `post`, `put`, `patch`, `del`) default their return type to `T = any`. Every call site that omits the type parameter silently bypasses TypeScript's type checker. Affected callers include `playlistService.ts:126` (accesses `.added_count` on untyped result) and `processingService.ts:207` (declared return type accepted without structural validation). The sibling `useRestAPI.ts` correctly defaults to `T = unknown`.
- **Evidence**:
  ```typescript
  export async function get<T = any>(endpoint: string, ...): Promise<T>
  // playlistService.ts:126 — T not specified → any → no type error
  const data = await post(ENDPOINTS.ADD_PLAYLIST_TRACK(playlistId), { track_ids });
  return data.added_count;  // any — backend rename produces no TS error
  ```
- **Impact**: Backend response shape regressions are invisible to TypeScript. `processingService.ts` creates a false sense of safety through its declared return type annotation.
- **Siblings**: `services/playlistService.ts:126`, `services/processingService.ts:207`, `hooks/player/usePlaybackQueue.ts:289,325`, `hooks/enhancement/useEnhancementControl.ts:223,288,332`.
- **Suggested Fix**: Change all six defaults to `T = unknown`. Call sites must then provide a type argument or narrow the result before use.

---

### DS-1: `index.css` CSS variable scale diverges from tokens on three dimensions
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/index.css:37-41,55-68,72-74`
- **Status**: NEW
- **Description**: Three sets of CSS custom properties defined in `index.css` are out of sync with `tokens.ts`: (1) Border-radius: `--radius-sm: 4px` vs `tokens.borderRadius.sm='8px'`, `--radius-md: 8px` vs `md='12px'`, `--radius-lg: 12px` vs `lg='16px'` — one scale step short at every level; (2) Colors: `--silver: #E2E8F0` not in tokens; `--aurora-pink: #F472B6` differs from `tokens.colors.audioSemantic.harmonic` (`#EC4899`); `body { color: var(--silver) }` affects default text; (3) Transitions: `--transition-normal: 200ms ease` uses plain `ease`, not the brand's `cubic-bezier`, and durations don't match `tokens.transitions`.
- **Evidence**:
  ```css
  --radius-sm: 4px;   /* tokens.borderRadius.sm = '8px' */
  --radius-md: 8px;   /* tokens.borderRadius.md = '12px' */
  --silver: #E2E8F0;  /* not in tokens — used in body { color } */
  --aurora-pink: #F472B6; /* tokens.audioSemantic.harmonic = #EC4899 */
  --transition-normal: 200ms ease;  /* tokens: 150ms cubic-bezier(...) */
  ```
- **Impact**: Any utility class or custom scrollbar using these vars renders with wrong radii (4px tighter), off-brand color, and non-brand easing. The `body` color fallback affects raw HTML elements.
- **Suggested Fix**: Replace `--radius-*` with `tokens.borderRadius.*` values; `--silver` with `tokens.colors.text.secondary`; `--aurora-pink` with `tokens.colors.audioSemantic.harmonic`; `--transition-normal/slow` with the brand cubic-bezier values from `tokens.transitions`.

---

### PF-1: `TrackGridView` grid path unvirtualized + inline `sx` defeats `TrackCard.memo`
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackGridView.tsx:53-86`
- **Status**: NEW (prior `FE-NEW-201` was reported but never filed as a GitHub issue; re-verified with additional detail)
- **Description**: The grid path calls `tracks.map(...)` with no `useVirtualizer`. The list-mode sibling (`TrackListViewContent`) correctly uses `@tanstack/react-virtual`. Additionally, the first 10 items receive an inline `sx` object with `animationDelay: \`${index * 0.05}s\`` — a new object identity on every parent render — defeating `TrackCard`'s `React.memo`. Every Redux state change (including the 100ms position tick from `usePlayNormal`) re-renders all 10 first-page wrappers.
- **Evidence**:
  ```tsx
  {tracks.map((track, index) => (
    <Grid2
      sx={index < 10 ? { animationDelay: `${index * 0.05}s` } : undefined}
    >
      <TrackCard ... />  // React.memo defeated by new sx reference
    </Grid2>
  ))}
  ```
- **Impact**: A 1,000-track library renders ~1,000 DOM nodes. The inline `sx` causes 10 memo busts on every state change.
- **Suggested Fix**: Apply `useGridVirtualizer` (already available in the codebase). Hoist animation styles to a stable `ENTRY_ANIMATION_STYLES` constant array.

---

### PF-2: `CozyAlbumGrid` / `EraSection` inline `onHoverEnter` creates new function refs per virtualizer tick
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:281,311`, `EraSection.tsx:106`
- **Status**: NEW
- **Description**: Both the virtualized and fallback paths pass `onHoverEnter` as an inline arrow `(id) => onAlbumHover(id, album.title, album.artist)` created inside `rowAlbums.map()`. A new function reference is produced on every virtualizer tick, defeating `AlbumCard`'s `React.memo`. The `onClick` equivalent was fixed in #3603 but the hover path was missed.
- **Evidence**:
  ```tsx
  // CozyAlbumGrid.tsx:281
  onHoverEnter={(id) => onAlbumHover(id, album.title, album.artist)}
  // new lambda on every virtualizer scroll tick → AlbumCard.memo always misses
  ```
- **Impact**: During scroll, hover over `AlbumCharacterPane` (which drives rAF updates), or any parent state change, all visible album cards re-render unnecessarily.
- **Suggested Fix**: Move hover binding into `AlbumCard` itself so it calls `onAlbumHover(albumId, title, artist)` from its own stable reference — mirroring the already-fixed `onClick` pattern.

---

### A11Y-1: `MetadataEditorDialog` missing `role="dialog"`, `aria-modal`, focus trap, and label association
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/MetadataEditorDialog.tsx:100-183`
- **Status**: NEW
- **Description**: The dialog renders as a raw `<div>` overlay with no `role="dialog"`, no `aria-modal="true"`, no `aria-labelledby` (the `<h2>` at line 105 has no `id`), no focus trap, and no focus-restoration on close. `ClearQueueDialog` and `ConfirmationDialog` implement all of these correctly via `useDialogAccessibility`. The five form fields also have no `htmlFor`/`id` association (A11Y-10).
- **Evidence**:
  ```tsx
  <div style={styles.overlay}>
    <div style={styles.dialog}>
      <h2 style={styles.title}>Edit Metadata</h2>  // no id
      // no role, no aria-modal, no aria-labelledby, no focus trap
  ```
- **Impact**: Screen readers do not announce the dialog as a modal context. Keyboard users can Tab past the dialog into the obscured background page. Focus is not returned to the triggering element after close.
- **Suggested Fix**: Apply `useDialogAccessibility` hook. Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby="metadata-dialog-title"` to the inner `<div>`. Add `id="metadata-dialog-title"` to the `<h2>`.

---

### A11Y-6: `ArtistTrackRow` interactive table row has no keyboard activation
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/ArtistTrackRow.tsx:29-77`
- **Status**: NEW
- **Description**: `StyledTableRow` (`<tr>`) has an `onClick` handler but no `tabIndex`, no `onKeyDown`, and no `aria-label`. Keyboard-only users cannot play tracks in the artist detail view. `TrackRow.tsx` and `QueueTrackItem.tsx` correctly implement `tabIndex={0}`, `onKeyDown` with Enter/Space, and `aria-label`.
- **Evidence**:
  ```tsx
  <StyledTableRow onClick={() => onTrackClick(track)}>
    // no tabIndex, no onKeyDown, no aria-label
  ```
- **Impact**: Keyboard-only users cannot activate any track in the Artist detail tracks table. WCAG 2.1.1 Level A.
- **Siblings**: `TrackTableRowItem.tsx:54` — same pattern.
- **Suggested Fix**: Add `tabIndex={0}`, `aria-label={\`Play ${track.title}\`}`, and `onKeyDown={(e) => e.key === 'Enter' || e.key === ' ' ? onTrackClick(track) : null}`.

---

### A11Y-7: Recommendation panel "Add" buttons are hover-only and unreachable by keyboard
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueueRecommendationsPanel/RecommendationTab.tsx:51-58`, `DiscoveryTab.tsx:39-47`, `NewArtistsTab.tsx:50-57`
- **Status**: NEW
- **Description**: The "Add to queue" (`+`) button in all three recommendation tabs is rendered only when `hoveredId === item.id` — it never appears on keyboard focus. It also uses only `title=` for its accessible name, not `aria-label`.
- **Evidence**:
  ```tsx
  {hoveredId === rec.track.id && (
    <button title="Add to queue">+</button>
    // rendered on hover only — unreachable via Tab/keyboard
  )}
  ```
- **Impact**: Keyboard-only users and screen reader users cannot add any track from the "For You", "Discover", or "New Artists" tabs. WCAG 2.1.1 Level A.
- **Suggested Fix**: Show the button when focused as well as hovered. Add `aria-label={\`Add ${track.title} to queue\`}`. Mirror `QueueTrackItem.tsx`'s hover+focus approach.

---

### TC-1: `usePlayNormal` test suite broken — mock missing `setResumePositionGetter` (all 18 tests fail)
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/enhancement/__tests__/usePlayNormal.test.ts:220-228`
- **Status**: NEW (sibling regression of FE-NEW-231 / #2601 pattern, fixed for `usePlayEnhanced` but not `usePlayNormal`)
- **Description**: The per-test `useWebSocketContext` mock omits `setResumePositionGetter`. `usePlayNormal.ts:639` calls `wsContext.setResumePositionGetter('play_normal', ...)` unconditionally on every mount. Every `renderHook(() => usePlayNormal(), ...)` throws `TypeError: wsContext.setResumePositionGetter is not a function`. The entire 18-test suite is silently broken.
- **Evidence**:
  ```ts
  // test mock (line 220-228) — missing field:
  vi.mocked(useWebSocketContext).mockReturnValue({
    isConnected: mockWsConnected,
    send: mockSend,
    subscribe: vi.fn(),
  } as any);  // no setResumePositionGetter

  // production hook (line 639) — unconditional call:
  wsContext.setResumePositionGetter('play_normal', () =>
    playbackEngineRef.current?.getCurrentPlaybackTime() ?? 0
  );
  ```
- **Impact**: Normal (non-enhanced) PCM streaming — the fallback path for every track play — has zero effective test coverage.
- **Suggested Fix**: Add `setResumePositionGetter: vi.fn()` and `reissueActiveStreamAs: vi.fn(() => false)` to the mock. Extract a shared `makeMockWsContext()` factory (mirroring `usePlayEnhanced.test.ts:231-254`).

---

### TC-2: `queueSlice` repeat-mode reducer branches completely untested
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/store/slices/__tests__/queueSlice.test.ts:161-184`
- **Status**: NEW
- **Description**: `queueSlice.ts` implements `repeatMode='one'` (stay on current) and `repeatMode='all'` (wrap to index 0) branches in both `nextTrack` and `previousTrack`. Only the `'off'` path is tested. `setIsShuffled` and `setRepeatMode` action creators are also absent from the test file.
- **Evidence**:
  ```ts
  nextTrack(state) {
    if (state.repeatMode === 'one') return;       // ← never tested
    } else if (state.repeatMode === 'all') {       // ← never tested
      state.currentIndex = 0;
    }
  }
  ```
- **Impact**: Bugs in repeat-one and repeat-all modes (e.g., track advancing when it should stay, not wrapping at end) will not be caught.
- **Suggested Fix**: Add `repeatMode='one'` and `repeatMode='all'` test cases for both `nextTrack` and `previousTrack`. Add `setIsShuffled`/`setRepeatMode` action tests.

---

### TC-3: `streaming-mse.test.tsx` runs 20 tests against an internal fixture, not production code
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/streaming-audio/streaming-mse.test.tsx:17,304-424`
- **Status**: NEW
- **Description**: The file-level JSDoc claims "SKIPPED" but has no `describe.skip`. The 20 tests run on every CI pass — but they exercise a standalone `TestMSEPlayer` / `MockMediaSource` / `MockSourceBuffer` entirely defined within the test file. No production module is imported. `AudioPlaybackEngine`, `PCMStreamBuffer`, and WebM streaming are never loaded.
- **Evidence**:
  ```ts
  class TestMSEPlayer {   // defined in the test file itself
    mediaSource: MockMediaSource | null = null;
    ...
  }
  // No import of any @/services or @/hooks module
  ```
- **Impact**: 20 CI "green" tests prove nothing about the actual streaming pipeline. Real WebM buffer overflow, sourceBuffer contention, and network recovery bugs are completely undetected.
- **Suggested Fix**: Convert to a real integration test importing `AudioPlaybackEngine` against a mock `AudioContext`, or mark the file `describe.skip('self-contained fixture — not a production test')` and create a separate integration test.

---

### MEDIUM

---

### RS-1: `setCurrentTime` dispatched before `setDuration` — clamps position to 0 on cold start
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:92-97`
- **Status**: NEW
- **Description**: The `player_state` handler dispatches `setCurrentTime(state.current_time)` at line 93 before `setDuration(state.duration)` at line 97. The `setCurrentTime` reducer clamps to `Math.min(payload, state.duration)`. On a cold start or reconnect when `state.duration` is still the previous track's value (or 0), `currentTime` is silently clamped to the wrong value. The subsequent `setDuration` update does not recalculate it.
- **Evidence**:
  ```ts
  dispatch(setCurrentTime(state.current_time));  // line 93 — clamps with stale duration
  dispatch(setDuration(state.duration));           // line 97 — too late
  ```
- **Suggested Fix**: Swap the dispatch order — `setDuration` first, then `setCurrentTime`.

---

### RS-5: `position_changed` WebSocket messages silently ignored — Redux `currentTime` never updates during playback
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:57-149`, `auralis-web/backend/core/state_manager.py:267-273`
- **Status**: NEW
- **Description**: The backend sends `{ type: "position_changed", data: { position: <float> } }` every second during playback. `usePlayerStateSync` subscribes only to `'player_state'`. No frontend code subscribes to `'position_changed'`. `redux.player.currentTime` is frozen between state-change events. The comment at `usePlaybackControl.ts:276` claiming "Server broadcasts 'position_changed' which updates the Redux player slice" is incorrect.
- **Evidence**:
  ```ts
  // usePlayerStateSync.ts:63 — only subscribes to 'player_state'
  const unsubscribe = subscribe('player_state', (message) => { ... });
  // No subscribe('position_changed', ...) anywhere in src/
  ```
- **Impact**: `selectCurrentTime`, `selectFormattedTime`, and `usePlaybackProgress` all serve stale data during active playback. The main progress bar is unaffected (uses streaming-engine local time), but any component reading from Redux position is frozen.
- **Suggested Fix**: Add `subscribe('position_changed', msg => dispatch(setCurrentTime(msg.data.position)))` in `usePlayerStateSync`. Remove the stale comment in `usePlaybackControl.ts:276`.

---

### CQ-2: `QueueStatisticsPanel` is 523 lines with 4 embedded sub-components and a 217-line styles block
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueueStatisticsPanel.tsx:1-523`
- **Status**: NEW
- **Suggested Fix**: Move `styles` to `QueueStatisticsPanel.styles.ts`. Extract `StatItem`, `StatRow`, `TopItemRow`, `QualityRating` to individual files under a `QueueStatisticsPanel/` directory.

---

### CQ-3: `StreamingProgressBar` is 474 lines with domain-math computations mixed into the component
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/enhancement/StreamingProgressBar.tsx:1-474`
- **Status**: NEW
- **Siblings**: `CacheStatsDashboard.tsx` (422 lines), `CacheHealthMonitor.tsx` (369 lines), `ConnectionStatusIndicator.tsx` (478 lines) — same pattern.
- **Suggested Fix**: Extract the 5 buffer-metric `useMemo` calls into a `useStreamingProgressMetrics` hook. Move styles to a `.styles.ts` sidecar.

---

### CQ-4: `onTrackPlay` prop drills 4+ component levels instead of a leaf-level hook
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:336`, `components/library/CozyLibraryView.tsx:41`, `components/library/Views/LibraryViewRouter.tsx:54`, `components/library/Details/AlbumDetailView.tsx:36`
- **Status**: NEW
- **Suggested Fix**: Expose a `usePlayTrack` hook callable at the leaf. Remove `onTrackPlay` from all intermediate interfaces.

---

### CQ-5: `CacheManagementPanel` calls `fetch()` directly without AbortController — post-unmount state update
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/shared/CacheManagementPanel/CacheManagementPanel.tsx:88-98`
- **Status**: NEW
- **Suggested Fix**: Add `mountedRef` guard. Replace raw `fetch()` with `useStandardizedAPI`.

---

### HC-1: `useEnhancedPlaybackShortcuts` — inline callbacks in deps cause listener churn and keystroke drops
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlaybackShortcuts.ts:111-172`
- **Status**: NEW
- **Description**: Four caller-supplied callbacks in `handleKeyDown`'s dep array cause the `keydown` listener to be torn down and re-added on every parent render. Keystrokes fired during the gap are silently dropped.
- **Suggested Fix**: Store each callback in a ref updated on every render, remove them from `handleKeyDown`'s dep array — matching the `intensityRef` pattern already used at line 105.

---

### HC-4: `useAudioVisualization` — animation-loop effect runs before analyser-init effect, causing a one-frame gap
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/audio/useAudioVisualization.ts:152-308`
- **Status**: NEW
- **Description**: The animation-loop effect (declared second, line 263) runs before the analyser-init effect (declared first, line 152) when both fire on `isAudioActive` transition. The first animation frame always fires with `analyserRef.current === null`, causing a one-frame visualization stutter on every play event.
- **Suggested Fix**: Merge analyser-init into the animation-loop effect, or swap declaration order so the init effect appears first.

---

### HC-5: `useLibraryWithStats` broad `eslint-disable` suppresses real stale-closure risk on `fetchTracks`
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:390-406`
- **Status**: NEW
- **Suggested Fix**: Stabilize `fetchTracks` by moving toast functions into refs so they can be removed from `fetchTracks`'s deps. Then remove the `eslint-disable` and add the functions to the effect deps.

---

### TS-2: `WebSocketContext` stashes `AudioChunkMetaMessage` typed as `AudioChunkMessage` — `samples` required but absent; `seq` field lost
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx:111,316`, `types/websocket.ts:461-498`
- **Status**: NEW
- **Suggested Fix**: Make `samples?: string` optional in `AudioChunkMessage.data`. Add `seq?: number`. Type `pendingAudioChunkMeta` as `AudioChunkMetaMessage | null`.

---

### TS-3: `ThemeContext` casts `localStorage` string to `ThemeMode` without validation — invalid stored value silently applies wrong theme
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/contexts/ThemeContext.tsx:25-26`
- **Status**: NEW
- **Evidence**:
  ```typescript
  return (savedTheme as ThemeMode) || 'dark';
  // 'system', 'auto', 'Light' all pass as truthy → wrong palette
  ```
- **Suggested Fix**: `const VALID: ThemeMode[] = ['light', 'dark']; return VALID.includes(savedTheme as ThemeMode) ? (savedTheme as ThemeMode) : 'dark';`

---

### TS-4: `types/domain.ts` `PlayerState` mixes snake_case and camelCase fields
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/domain.ts:132-147`, `types/api.ts:79-90`
- **Status**: NEW
- **Description**: `gapless_enabled`, `crossfade_enabled`, `crossfade_duration` use backend snake_case while all other fields are camelCase. Components accessing `state.gaplessEnabled` get `undefined` silently; components using `state.gapless_enabled` against the Redux `playerSlice` get `undefined` silently.
- **Siblings**: `auralis-web/frontend/src/types/api.ts:87-89`, `services/settingsService.ts:22-24`.
- **Suggested Fix**: Rename to `gaplessEnabled`, `crossfadeEnabled`, `crossfadeDuration` in both `domain.ts` and `api.ts`.

---

### DS-2: `Spacing.styles.ts` defines a parallel spacing scale not derived from `tokens.spacing`
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Styles/Spacing.styles.ts:29-135`
- **Status**: NEW
- **Description**: `spacingMedium='16px'` vs `tokens.spacing.md='12px'`; `spacingLarge='24px'` vs `tokens.spacing.lg='20px'` — every step is 4–8px larger than the token scale.
- **Suggested Fix**: Replace constants with `tokens.spacing.*` references.

---

### DS-3: `glassEffects.strong/minimal` use raw `rgba()` backgrounds not in any token
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:101-117`
- **Status**: NEW
- **Suggested Fix**: Add `tokens.glass.strong.backgroundDark/Light` and `tokens.glass.medium.backgroundDark/Light`. Reference from `glassEffects`.

---

### DS-4: MUI palette shades + `neon.purple` in `themeConfig.ts` are unexported magic hex literals
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:52,144-147`
- **Status**: NEW
- **Suggested Fix**: Add `tokens.colors.accent.primaryLight/Dark` and `secondaryLight/Dark`. Add `tokens.colors.audioSemantic.harmonicDark` for `neon.purple`.

---

### DS-5: Scattered `rgba()` glass backgrounds across 9+ component files — no token equivalent
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: Multiple files
- **Status**: NEW
- **Siblings**: `AppTopBar.styles.ts:11`, `MobileSidebarDrawer.tsx:53`, `SidebarStyles.ts:93`, `AppContainer.tsx:77`, `Player.styles.ts:21`, `TrackCardOverlay.tsx:84-85`, `TrackCardStyles.ts:75`, `ArtistList.styles.ts:42,49`, `TrackListView.styles.ts:6`, `AlbumsTab.tsx:48`, `DroppablePlaylist.styles.ts:25`, `ArtworkContainer.tsx:33`, `EnhancementToggleStyles.ts:69,71`
- **Suggested Fix**: Extend `tokens.glass.*` with `starfield` preset (0.45–0.65 range) and `tokens.colors.opacityScale.white.ultraLight` (0.03). Wire all sites through tokens.

---

### AC-1: `useQuery` helper in `useRestAPI.ts` has a broken `catch` handler — crashes on any error
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:370`
- **Status**: NEW
- **Evidence**:
  ```ts
  setErrorApiErrorHandler.parse(err);  // should be: setError(ApiErrorHandler.parse(err))
  ```
- **Suggested Fix**: Fix to `setError(ApiErrorHandler.parse(err))`. Also export `useQuery` from the index or delete it to make its status explicit.

---

### AC-2: `usePaginatedAPI` fires initial fetch with no AbortController — setState on unmounted component
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:279-281`
- **Status**: NEW
- **Suggested Fix**: Mirror the `AbortController` pattern from `useStandardizedAPI.ts:167-174`.

---

### AC-3: `usePlaybackState.handlePlayTrack` ignores `response.ok` — playback proceeds on failed queue POST
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/usePlaybackState.ts:30-56`
- **Status**: NEW
- **Evidence**:
  ```ts
  await fetch('/api/player/queue', { method: 'POST', ... });
  // response.ok never checked — always reaches:
  wsContext.send({ type: 'play_enhanced', ... });
  success(`Now playing: ${track.title}`);
  ```
- **Suggested Fix**: Check `if (!response.ok) throw new Error(...)` after the fetch. Surface the error via the `error` toaster.

---

### PF-3: `AlbumCharacterPane.containerStyles` rebuilt every rAF frame during playback decay
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/AlbumCharacterPane.tsx:124-144`
- **Status**: NEW
- **Description**: A plain-object `containerStyles` depends on `glowIntensity` which changes ~60×/sec during the 2.5-second playback-stop decay. Not wrapped in `useMemo`. Causes Emotion to re-hash styles on every rAF tick. Five child visualization sub-components (`FloatingParticles`, `WaveformVisualization`, `GlowingArc`, `CharacterTags`, `EnergyField`) are also not memoized.
- **Suggested Fix**: Wrap `containerStyles` in `useMemo`. Round `glowIntensity` to 2 decimal places. Wrap visualization sub-components in `React.memo`.

---

### PF-4: `useEnhancementControl` fires 3 redundant API fetches on concurrent mount
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:171-191`
- **Status**: NEW
- **Description**: Three simultaneous callers (`EnhancementPane`, `Expanded`, `AlbumCharacterPane`) each independently fetch `/api/player/enhancement/status` on mount and subscribe their own `enhancement_settings_changed` WS handler. No shared cache exists.
- **Suggested Fix**: Lift enhancement state to Redux (already partially present as `state.player.preset`) or use React Query `useQuery` with `queryKey: ['enhancement-status']` and `staleTime: Infinity`.

---

### PF-5: `SimilarTracksModal` and `EditMetadataDialog` eagerly imported in `CozyLibraryView`
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:22-23`
- **Status**: NEW
- **Suggested Fix**: Replace both static imports with `lazy(() => import(...))` and wrap conditional render sites in `<Suspense fallback={null}>`.

---

### PF-6: Artist list grows unbounded — no DOM windowing across `InfiniteScroll + map()`
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/ArtistListContent.tsx:114-122`, `ArtistSection.tsx:32`
- **Status**: NEW (FE-NEW-206 fixed `memo` in #3607; virtualization gap remains)
- **Suggested Fix**: Flatten `[{type:'header'}, {type:'artist'}]` into a single `useVirtualizer` with variable height items.

---

### A11Y-2: `EnhancementPane` close button has only `title`, no `aria-label`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/enhancement/EnhancementPane.tsx:167`
- **Status**: NEW
- **Suggested Fix**: Replace `title=` with `aria-label="Close detailed controls"`.

---

### A11Y-3: `QueueRecommendationsPanel` tab buttons missing `role="tablist"`, `role="tab"`, `aria-selected`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueueRecommendationsPanel/QueueRecommendationsPanel.tsx:77-117`
- **Status**: NEW
- **Suggested Fix**: Add `role="tablist"` to container, `role="tab"` + `aria-selected={...}` to each button, `role="tabpanel" aria-labelledby={...}` to each content panel.

---

### A11Y-4: `ThemeToggle` icon button has no accessible name
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/ui/ThemeToggle.tsx:41-66`
- **Status**: NEW
- **Suggested Fix**: Add `aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}` to `ThemeToggleButton`.

---

### A11Y-5: `EnhancementToggle.ButtonVariant` missing `aria-pressed`
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/shared/EnhancementToggle/ButtonVariant.tsx:33-37`
- **Status**: NEW
- **Suggested Fix**: Add `aria-pressed={isEnabled}`. Simplify `aria-label` to stable "Audio enhancement".

---

### A11Y-8: `CozyAlbumGrid` `role="grid"` missing required `role="row"` / `role="gridcell"` descendants
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:133`
- **Status**: NEW
- **Suggested Fix**: Add `role="row"` to each row `<div>` and `role="gridcell"` to each album wrapper. Alternatively, change to `role="list"` + `role="listitem"` if two-dimensional navigation is not intended.

---

### TC-4: `matchMedia` mock returns `matches = true` for mobile breakpoints on simulated desktop
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/test/setup.ts:104-116`
- **Status**: NEW
- **Description**: The comment says "Default to desktop size (1920×1080)" but the mock returns `matches = true` for `max-width: 400px` (xs) and `max-width: 600px` (sm) — the opposite of correct. All MUI components using `useMediaQuery(theme.breakpoints.down('xs'/'sm'))` always see the mobile branch in tests.
- **Suggested Fix**: Change both `true` values to `false`. Add a per-test helper `setMobileBreakpoint(breakpoint)` for tests needing mobile simulation.

---

### TC-5: `MockWebSocketProvider` in `test-utils.tsx` is dead — wraps a different context than components read
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/test/test-utils.tsx:42-67`
- **Status**: NEW
- **Suggested Fix**: Remove `MockWebSocketContext`, `MockWebSocketProvider`, and the re-exported `useWebSocketContext` from `test-utils.tsx`. Use `vi.mocked(useWebSocketContext)` from the actual context module.

---

### TC-6: `usePlayerStateSync` test mock shape incomplete — latent breakage time-bomb
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/player/__tests__/usePlayerStateSync.test.ts:75-88`
- **Status**: NEW
- **Suggested Fix**: Extract a shared `makeMockWsContext(overrides?)` factory covering all `WebSocketContextValue` fields.

---

### TC-7: `AudioPlaybackEngine` (595 lines) has zero unit tests
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:1-595`
- **Status**: Existing: #2601 (partial — `usePlayEnhanced` tests added; `AudioPlaybackEngine` itself remains untested)
- **Suggested Fix**: Add `AudioPlaybackEngine.test.ts` using `vi.stubGlobal('AudioContext', MockAudioContext)`.

---

### LOW

---

### RS-2: `stop()` optimistic rollback is unreachable dead code — `send()` never throws
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:208-257`
- **Status**: NEW

---

### RS-3: `updateCache()` reducer bypasses `setCacheStats.prepare()` per-track Map stripping
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/cacheSlice.ts:76-99`
- **Status**: NEW
- **Suggested Fix**: Apply `{ ...params.stats, tracks: {} }` stripping in `updateCache.prepare()`.

---

### RS-4: `createMemoizedSelector` cache never hits when compute function returns `undefined`
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/selectors/index.ts:427-443`
- **Status**: NEW
- **Suggested Fix**: Change guard from `lastResult !== undefined` to `lastTuple !== undefined`.

---

### HC-3: `useEnhancementControl` — three unnecessary one-field `useEffect` synchronizers
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:204,210,212`
- **Status**: NEW
- **Suggested Fix**: Replace with direct `ref.current = value` assignments at hook body level.

---

### HC-6: `usePlayNormal` 100ms `setCurrentTime` interval runs unconditionally when idle
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:592-598`
- **Status**: NEW
- **Suggested Fix**: Gate interval on `isPlaying` matching `usePlayEnhanced` at line 858-867.

---

### HC-7: `useArtworkUpdates` strict-mode refcount window (dev-only)
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useArtworkUpdates.ts:100-119`
- **Status**: NEW — dev-only impact (production Strict Mode is off)

---

### HC-8: `useMasteringRecommendation` rapid `trackId` change causes one-render `isLoading` flicker
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useMasteringRecommendation.ts:67-102`
- **Status**: NEW
- **Suggested Fix**: Remove the conditional `setIsLoading(false)` from the cleanup; let the new effect invocation manage its own loading lifecycle.

---

### HC-9: `useStandardizedAPI.refetch` public type hides `signal` parameter — manual refetches not cancelled on unmount
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useStandardizedAPI.ts:176-182`
- **Status**: NEW

---

### HC-10: `useLibraryQuery.fetchMore` advances `offset` before confirming non-empty response
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:307-338`
- **Status**: NEW
- **Suggested Fix**: Gate `setOffset(nextOffset)` inside `if (items.length > 0)`.

---

### HC-11: `useQueueStatistics` / `useQueueSearch` module-level `_warned` flags persist across HMR and test runs
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueStatistics.ts:115`, `useQueueSearch.ts:169`
- **Status**: NEW

---

### HC-12: `usePlayNormal` double teardown on explicit `stopPlayback()` + unmount — idempotent, no crash
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:556-607`
- **Status**: NEW

---

### TS-5: `HealthCheckResponse` declares fields not in the actual backend health endpoint
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/api.ts:329-336`
- **Status**: NEW

---

### TS-6: `settingsService.getSettings()` annotates intermediate result as `any` — negates generic type fix
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/services/settingsService.ts:97`
- **Status**: NEW

---

### TS-7: `SmoothAnimationEngine` uses unguarded `as number` / `as number[]` casts across 9 sites
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/SmoothAnimationEngine.ts:557-578`
- **Status**: NEW

---

### TS-8: `queue_shuffler.ts` switch on `ShuffleMode` has no `never`-exhaustiveness check
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/queue/queue_shuffler.ts:60-75`
- **Status**: NEW

---

### DS-6 through DS-12 (Design System — LOW)

- **DS-6**: `Player.styles.ts` error banner uses raw `rgba(239,68,68,*)` instead of `tokens.colors.utility.errorBg` variants
- **DS-7**: `Input.tsx` and `SegmentedControl.tsx` primitives use raw `rgba()` for background states below `tokens.opacityScale.white.veryLight`
- **DS-8**: Keyframe animations in `design-system/animations/index.ts` and `AlbumCharacterPane/animations.ts` embed raw `rgba(115,102,240,*)` outside tokens
- **DS-9**: 13 hardcoded rem/px font sizes bypass `tokens.typography.fontSize.*` — one (`0.625rem`/10px) is below the WCAG AA floor
- **DS-10**: `globalStyles.ts` `@keyframes glow` and `::selection` use raw `rgba(115,102,240,*)` — `::selection` could trivially use `tokens.colors.opacityScale.accent.strong`
- **DS-11**: `ShuffleModeSelector.module.css` duplicates `tokens.transitions.hover_out` as a string literal
- **DS-12**: `themeConfig.ts` gradient stop `#5A5CC4` duplicated before `PRIMARY_DARK` constant is declared

---

### AC-4 through AC-6 (API Client — LOW)

- **AC-4**: `useLibraryWithStats.scanFolder` fetch has no timeout or AbortController; `finally` block calls setState on potentially-unmounted component
- **AC-5**: `useInfiniteAlbums`, `usePlayNormal`, `usePlayEnhanced` construct URLs as `` `${API_BASE_URL}/...` `` bypassing `getApiUrl()` path normalization
- **AC-6**: `useAppDragDrop` surfaces all fetch errors as the same generic toast — backend `detail` field discarded

---

### CQ-6, CQ-7 (Component Quality — LOW)

- **CQ-6**: `CacheStatsDashboard.PercentageDisplay` `opacity: 0.2` makes the percentage text inside the circle invisible (use `background: ${color}20` instead)
- **CQ-7**: `PlayerEnhancementPanel` contains ~150 lines of commented-out dead code (lines 210–278)

---

### PF-7, PF-8 (Performance — LOW)

- **PF-7**: `useQueueState` / `useCacheState` / `useConnectionState` return new container-object references on every slice mutation — potential memo-busting for downstream consumers
- **PF-8**: `PlayerBarV2` artwork `<img>` missing `loading="lazy"` and explicit dimensions — causes layout shift

---

### A11Y-9, A11Y-10, A11Y-11 (Accessibility — LOW)

- **A11Y-9**: `TrackDisplay.tsx:129`, `GlobalSearch.tsx:67`, `ariaUtilities.ts:312` use deprecated `clip: rect(0,0,0,0)` — should be `clipPath: 'inset(50%)'` per fix #3651 applied only to `ProgressBar.styles.ts`
- **A11Y-10**: `MetadataEditorDialog` five `<label>` elements have no `htmlFor` / inputs have no `id`
- **A11Y-11**: `NoArtworkButtons` two icon-only action buttons have no `aria-label`

---

### TC-8 through TC-10 (Test Coverage — LOW)

- **TC-8**: `useMasteringRecommendation` cache-hit test missing `expect(result.current.isLoading).toBe(false)` — no regression guard for FE-NEW-149 fix
- **TC-9**: `setup.ts` blanket `console.error` suppression silences "not wrapped in act" warnings project-wide — masks real async update bugs
- **TC-10**: Existing: #3654 — `usePlaybackQueue` real-time `queue_changed` WS path still untested

---

## Cross-dimension Relationships

### Root cause cluster 1: Shared WS context mock is incomplete across test suite
**TC-1 + TC-5 + TC-6** share the same root cause: the `WebSocketContextValue` mock shape is partially defined in three different places (`usePlayNormal.test.ts`, `test-utils.tsx`, `usePlayerStateSync.test.ts`), all missing `setResumePositionGetter`. Fix: create `test/mocks/websocketContext.ts` with a shared `makeMockWsContext()` factory.

### Root cause cluster 2: Position state not updating during playback
**RS-5** (no `position_changed` subscriber) + **RS-1** (wrong dispatch order clamps position to 0) both cause `redux.player.currentTime` to be wrong during active playback. Fix RS-5 first (adds the subscriber), then RS-1 (fixes the cold-start clamp).

### Root cause cluster 3: Unstable references defeating React.memo
**PF-1** (inline `sx` in `TrackGridView`) + **PF-2** (inline arrow in `CozyAlbumGrid`) both create new object/function references on every render cycle, defeating `React.memo` on the immediate children. Same pattern as the prior-fixed FE-NEW-202 (AlbumGridContent onClick) and FE-NEW-203 (EnhancementControl).

### Root cause cluster 4: `apiRequest.ts T = any` propagation
**TS-1** (the source) propagates through **AC-3** (no `response.ok` check → typed result is `any` → success toast fires regardless) and creates invisible holes in **DS-9** (font size tokens not enforced because the `settingsService` in **TS-6** also uses `any`).

### Root cause cluster 5: Design system `rgba()` proliferation
**DS-1** (CSS vars diverge) + **DS-3** (glass effects raw rgba) + **DS-5** (scattered component rgba) + **DS-7** (primitives rgba) + **DS-8** (keyframe rgba) + **DS-10** (globalStyles rgba) all stem from missing token coverage for glass-surface opacities below `tokens.glass.subtle` and above `tokens.glass.medium`. A single pass to add `tokens.glass.starfield`, `tokens.colors.opacityScale.white.ultraLight/micro`, and `tokens.colors.utility.errorBgMedium` would unblock all six.

---

## Prioritized Fix Order

### Tier 1 — Fix before next release

| Priority | ID | Effort | Why |
|---|---|---|---|
| 1 | **CQ-1** | M | CRITICAL hook violation — crash risk on albums/artists switch |
| 2 | **TC-1** | S | Unlocks 18 dead normal-playback tests — one line change |
| 3 | **TC-4** | S | Two `true → false` changes fix all tests running in wrong viewport |
| 4 | **RS-5** | S | Frozen Redux position counter — subscribe to `position_changed` in `usePlayerStateSync` |
| 5 | **AC-3** | S | Silent playback-on-failed-queue — add `response.ok` check |
| 6 | **A11Y-1** | M | Dialog ARIA pattern — apply `useDialogAccessibility` (already exists for other dialogs) |
| 7 | **TC-3** | S | Mark streaming fixture as `describe.skip` or convert to real production test |

### Tier 2 — High-value, low-risk fixes

| Priority | ID | Effort | Why |
|---|---|---|---|
| 8 | **TS-1** | S | Change 6 `T = any` defaults to `T = unknown` in `apiRequest.ts` |
| 9 | **TC-2** | S | Add 4 `queueSlice` repeat-mode test cases |
| 10 | **RS-1** | S | Swap `setDuration` / `setCurrentTime` dispatch order |
| 11 | **A11Y-6** | S | Add `tabIndex`, `onKeyDown`, `aria-label` to `ArtistTrackRow` |
| 12 | **A11Y-7** | S | Show recommendation "Add" buttons on focus; add `aria-label` |
| 13 | **DS-1** | S | Align `index.css` CSS vars with `tokens.*` |
| 14 | **PF-1** | M | Virtualize `TrackGridView` grid path; hoist animation `sx` constant |
| 15 | **HC-2** | S | Add `isActive` guard to `usePlaybackQueue.fetchInitialQueue` |

### Tier 3 — Medium-term cleanup

| Priority | Group | Findings |
|---|---|---|
| 16 | WS mock factory | TC-5, TC-6 |
| 17 | Performance-memo | PF-2, PF-3, PF-4, PF-5 |
| 18 | Accessibility | A11Y-3, A11Y-4, A11Y-5, A11Y-8 |
| 19 | Type safety | TS-2, TS-3, TS-4 |
| 20 | Design system (glass) | DS-3, DS-5, DS-7, then DS-6, DS-8–DS-12 |

### Tier 4 — Low / maintenance

API client patterns (AC-2, AC-4, AC-5, AC-6), hook cleanups (HC-3, HC-5 through HC-12), Redux latent issues (RS-2, RS-3, RS-4), component size (CQ-2, CQ-3, CQ-4), prop drilling (CQ-4), dead code (CQ-7), remaining type safety (TS-5–TS-8), performance tuning (PF-6, PF-7, PF-8), accessibility polish (A11Y-2, A11Y-9–A11Y-11), test hygiene (TC-7 through TC-10).
