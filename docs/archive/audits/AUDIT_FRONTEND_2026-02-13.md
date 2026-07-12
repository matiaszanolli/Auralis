# Frontend Audit Report — 2026-02-13

**Auditor**: Claude Opus 4.6
**Scope**: `auralis-web/frontend/src/` — React 18 + TypeScript + Vite + Redux Toolkit + MUI 5
**Prior audit**: 2026-02-12 (9 findings: F-01 through F-09, issues #2131-#2139)

---

## Executive Summary

**8 NEW findings** — 2 HIGH, 5 MEDIUM, 1 LOW

This audit builds on the prior frontend audit (2026-02-12) and 19 existing frontend-related issues. After thorough deduplication and code verification, 8 genuinely new issues were confirmed.

| Severity | Count | Key themes |
|----------|-------|------------|
| HIGH | 2 | TrackRow not memoized (O(n) re-renders), TrackList not virtualized (DOM bloat) |
| MEDIUM | 5 | Imperative DOM mutations, index keys, unstable callback deps, stale state reads, CSS !important |
| LOW | 1 | Unused virtualization dependency |

**Most impactful findings:**
1. **F2-H01**: `TrackRow` and its children lack `React.memo` despite receiving 10+ callback props. Every parent re-render causes O(n) row re-renders — with 1000 tracks and 100ms position updates, this means ~10,000 unnecessary re-renders/second.
2. **F2-H02**: `TrackList` renders all tracks directly to DOM without virtualization, despite `@tanstack/react-virtual` being installed in `package.json` but never imported. Large libraries cause DOM node bloat and scroll jank.

---

## New Findings (8)

### HIGH

### F2-H01: TrackRow Components Not Memoized Despite Receiving 10+ Callback Props
- **Severity**: HIGH
- **Dimension**: Performance / Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:48`
- **Status**: NEW
- **Description**: `TrackRow` is exported as a plain `React.FC` (line 48) without `React.memo`. It accepts 10+ props including object (`track`) and function props (`onPlay`, `onPause`, `onDoubleClick`, `onEditMetadata`, `onFindSimilar`, `onToggleFavorite`, `onShowAlbum`, `onShowArtist`, `onShowInfo`, `onDelete`). Each parent re-render causes ALL rows to re-render even when their data hasn't changed. Sub-components `TrackRowMetadata`, `TrackRowPlayButton`, and `TrackRowAlbumArt` are also unmemoized.
- **Evidence**:
```typescript
// TrackRow.tsx:48 — no React.memo
export const TrackRow: React.FC<TrackRowProps> = ({
  track,         // Object reference — changes on every parent render
  onPlay,        // Function — changes on every parent render unless memoized
  onPause,
  onDoubleClick,
  onEditMetadata,
  onFindSimilar,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  // ... 10+ props total
}) => { ... }
```
Only 17 of ~286 component files use `React.memo`. None of the list item components are memoized.
- **Impact**: In a library with 200 tracks, every Redux state change (including 100ms position updates) triggers 200 TrackRow re-renders. Combined with #2131 (factory selectors), this creates a render cascade: position update → selector runs → parent re-renders → all 200 rows re-render → each row calls 4 custom hooks.
- **Related**: Compounds #2131 (factory selectors) and #2137 (usePlaybackQueue callback recreation)
- **Suggested Fix**: Wrap `TrackRow` and its children with `React.memo` using custom comparator:
```typescript
export const TrackRow = React.memo<TrackRowProps>(({ track, ... }) => { ... },
  (prev, next) => prev.track.id === next.track.id
    && prev.isPlaying === next.isPlaying
    && prev.isCurrent === next.isCurrent
);
```

---

### F2-H02: TrackList Renders All Tracks to DOM Without Virtualization
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/TrackList.tsx:126`
- **Status**: NEW
- **Description**: `TrackList` renders all loaded tracks directly via `tracks.map(...)` (line 126) without using virtualization. The `@tanstack/react-virtual` package IS listed as a dependency in `package.json` but is never imported or used anywhere in the codebase. With infinite scroll loading 50 tracks per page, after scrolling through 20 pages the DOM contains 1000+ track elements simultaneously.
- **Evidence**:
```typescript
// TrackList.tsx:126 — direct DOM rendering, no virtualization
{tracks.map((track, index) => (
  <div
    key={`${track.id}-${index}`}
    ref={selectedIndex === index ? handleTrackSelect : null}
    onClick={() => handleTrackClick(track, index)}
    style={{ ... }}
    role="button"
    tabIndex={0}
  >
    ...
  </div>
))}

// package.json:14 — dependency installed but unused
"@tanstack/react-virtual": "^3.13.13"
```
- **Impact**: For a 1000-track library after scrolling: ~1000 DOM nodes, ~50MB+ DOM memory, scroll jank on mid-range devices. IntersectionObserver for infinite scroll adds more tracks but never removes old ones.
- **Suggested Fix**: Integrate `@tanstack/react-virtual` (already installed):
```typescript
import { useVirtualizer } from '@tanstack/react-virtual';
const virtualizer = useVirtualizer({
  count: tracks.length,
  getScrollElement: () => containerRef.current,
  estimateSize: () => 48,
});
```

---

### MEDIUM

### F2-M01: PlaybackControls Uses Imperative DOM Mutations for Hover States
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/PlaybackControls.tsx:109-129, 148-169, 184-205, 220-241, 256-277`
- **Status**: NEW
- **Description**: All 5 player buttons mutate `e.currentTarget.style.*` directly in `onMouseEnter`, `onMouseLeave`, `onFocus`, and `onBlur` handlers instead of using React state. This bypasses React's reconciliation, makes the component opaque to React DevTools, and breaks testing with `@testing-library` (can't query for state-based styles).
- **Evidence**:
```typescript
// PlaybackControls.tsx:109-129 — repeated for every button
onMouseEnter={(e) => {
  if (!isDisabled) {
    e.currentTarget.style.backgroundColor = tokens.colors.bg.tertiary;
    e.currentTarget.style.borderColor = tokens.colors.accent.primary;
    e.currentTarget.style.transform = 'scale(1.05)';
  }
}}
onMouseLeave={(e) => {
  e.currentTarget.style.backgroundColor = 'transparent';
  e.currentTarget.style.borderColor = tokens.colors.border.light;
  e.currentTarget.style.transform = 'scale(1)';
}}
```
Pattern repeated identically for Previous, Play, Pause, Next, and Stop buttons (5× duplication).
- **Impact**: Cannot test hover states via React Testing Library. Direct DOM mutations can conflict with CSS transitions. 5× code duplication for identical hover behavior.
- **Suggested Fix**: Use CSS `:hover` / `:focus` pseudo-classes via styled-components or MUI `sx` prop, or extract a shared `HoverableButton` component with React state.

---

### F2-M02: Index-Based React Keys on Dynamic Lists
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueueRecommendationsPanel.tsx:325`, `auralis-web/frontend/src/components/player/QueueStatisticsPanel.tsx:282`
- **Status**: NEW
- **Description**: Two components use `key={index}` on dynamic lists that can reorder or change. `QueueRecommendationsPanel.tsx:325` uses `key={index}` for artist cards. `QueueStatisticsPanel.tsx:282` uses `key={index}` for quality assessment issues. When items are added/removed/reordered, React recycles DOM nodes incorrectly.
- **Evidence**:
```typescript
// QueueRecommendationsPanel.tsx:325 — artist cards use index as key
{newArtists.map((artist, index) => (
  <div key={index} ...>
    {artist.artist}
  </div>
))}

// QueueStatisticsPanel.tsx:282 — issue items use index as key
{assessment.issues.map((issue, index) => (
  <div key={index} style={styles.issueItem}>
    • {issue}
  </div>
))}
```
Additionally, composite keys like `key={`${track.id}-${index}`}` at QueuePanel.tsx:222 and QueueRecommendationsPanel.tsx:215,273 include index unnecessarily.
- **Impact**: When recommendation list updates (new tracks recommended, user dismisses recommendation), hover state, animations, and any internal component state can transfer to the wrong item. For the artist cards, hover state tracking via `hoveredIndex` (line 328) is fragile.
- **Suggested Fix**: Use stable identifiers: `key={artist.artist}` for artists, `key={issue}` for string issues, `key={track.id}` for tracks (without index suffix).

---

### F2-M03: useOptimisticUpdate Execute Callback Has Unstable Dependencies
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useOptimisticUpdate.ts:52`
- **Status**: NEW
- **Description**: The `execute` callback depends on `[state, asyncOperation, options]` (line 52). The `state` value changes on every `execute()` call (since execute updates state). The `options` parameter is typically an object literal `{ onSuccess: ..., onError: ... }` from the caller, creating a new reference on every render. This makes `execute` unstable — it's recreated on every render and every execution.
- **Evidence**:
```typescript
// useOptimisticUpdate.ts:22-52
const execute = useCallback(
  async (optimisticValue: T, ...args: Args) => {
    const previousState = state;      // Captures state for rollback
    setState(optimisticValue);         // Changes state → recreates execute
    // ...
  },
  [state, asyncOperation, options]     // state changes on every execute()
);
```
- **Impact**: Components using `execute` in dependency arrays or passing it to memoized children see constant recreation. If `execute` is in a `useEffect` dependency that also triggers state changes, it creates an infinite loop. The `options` instability means even components that don't call execute still get recreated callbacks.
- **Suggested Fix**: Use `useRef` for state rollback instead of including `state` in dependencies:
```typescript
const stateRef = useRef(state);
stateRef.current = state;
const execute = useCallback(async (...) => {
  const previousState = stateRef.current;  // No state dependency
}, [asyncOperation]);  // options handled separately via ref
```

---

### F2-M04: websocketMiddleware NEXT/PREVIOUS Handler Reads Stale State Snapshot
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/middleware/websocketMiddleware.ts:105-123`
- **Status**: NEW
- **Description**: The NEXT and PREVIOUS message handlers dispatch `queueActions.nextTrack()` first, then read `state.queue.tracks[currentIndex ± 1]` to find the track. But `state` is the snapshot from BEFORE the dispatch. If `nextTrack()` modifies the tracks array (e.g., during shuffle), the lookup uses the old order and may set the wrong track as current.
- **Evidence**:
```typescript
// websocketMiddleware.ts:105-123
[MessageType.NEXT]: (_message, dispatch, state) => {
  const { currentIndex } = state.queue;         // Old index
  dispatch(queueActions.nextTrack());            // Updates store → new currentIndex
  const nextTrack = state.queue.tracks[currentIndex + 1]; // Reads OLD tracks array
  if (nextTrack) {
    dispatch(playerActions.setCurrentTrack(nextTrack));    // May be wrong track
  }
},

[MessageType.PREVIOUS]: (_message, dispatch, state) => {
  const { currentIndex } = state.queue;          // Old index
  dispatch(queueActions.previousTrack());
  const prevTrack = state.queue.tracks[currentIndex - 1]; // Reads OLD tracks array
  if (prevTrack) {
    dispatch(playerActions.setCurrentTrack(prevTrack));
  }
},
```
- **Impact**: During shuffled playback, pressing next/previous may play the wrong track. The two dispatches (`nextTrack` + `setCurrentTrack`) are not atomic — if the store is read between them, queue index and current track are temporarily inconsistent.
- **Suggested Fix**: Read the updated state after the first dispatch, or combine both updates into a single reducer action:
```typescript
[MessageType.NEXT]: (_message, dispatch, _state) => {
  dispatch(queueActions.nextTrackAndSetCurrent());
},
```

---

### F2-M05: CSS `!important` Overrides Indicate Specificity Issues
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/navigation/ViewToggle.tsx:24`, `auralis-web/frontend/src/components/shared/Toast/ToastItem.tsx:38`
- **Status**: NEW
- **Description**: Two components use `!important` to override MUI's default styles, indicating CSS specificity conflicts that were resolved by force rather than proper cascade management.
- **Evidence**:
```typescript
// ViewToggle.tsx:24 — overrides MUI ToggleButton border-radius
borderRadius: `${tokens.borderRadius.sm} !important`,

// ToastItem.tsx:38 — overrides MUI Snackbar positioning
sx={{
  top: `${24 + index * 70}px !important`,
  transition: 'top 0.3s ease',
}}
```
- **Impact**: MUI version upgrades may change internal specificity, breaking these overrides. The `!important` flag masks the root cause and makes debugging CSS issues harder. The toast positioning calculation (index × 70px) is also fragile — different toast heights break the stack.
- **Suggested Fix**: For ViewToggle, use MUI's `sx` prop with proper selector specificity or `&.MuiToggleButton-root` selector. For Toast, use a custom position manager or MUI's Snackbar `anchorOrigin` with auto-stacking.

---

### LOW

### F2-L01: @tanstack/react-virtual Dependency Installed But Never Used
- **Severity**: LOW
- **Dimension**: Code Quality
- **Location**: `auralis-web/frontend/package.json:14`
- **Status**: NEW
- **Description**: `@tanstack/react-virtual` version `^3.13.13` is listed in `package.json` dependencies but is never imported anywhere in the codebase. This adds ~12KB to the bundle (if not tree-shaken) and creates confusion about whether virtualization is implemented.
- **Evidence**:
```json
// package.json:14
"@tanstack/react-virtual": "^3.13.13",
```
```bash
# Grep across entire frontend source
$ grep -r "useVirtualizer\|react-virtual" src/
# (no results)
```
- **Impact**: Unused dependency adds to install time, lockfile complexity, and potential security surface. Developers may assume virtualization is active when it is not.
- **Related**: F2-H02 (TrackList not virtualized) — the fix for F2-H02 would make this dependency used.
- **Suggested Fix**: Either use the dependency (fix F2-H02) or remove it from `package.json` if not planned.

---

## Existing Findings — Previously Filed

All findings from the prior frontend audit (2026-02-12) remain open:

| Finding | Severity | Dimension | Issue |
|---------|----------|-----------|-------|
| Factory selectors return new references | HIGH | Redux State / Performance | #2131 |
| usePlayerStreaming drift threshold units | HIGH | Hook Correctness | Fixed in fb1bd4b1 |
| useWebSocketProtocol async IIFE cleanup | HIGH | Hook Correctness | #2133 |
| useWebSocketSubscription unsubscribe bug | MEDIUM | Hook Correctness | #2134 |
| Hardcoded color values bypass tokens | MEDIUM | Design System | #2135 |
| Sparse ARIA/accessibility attributes | MEDIUM | Accessibility | #2136 |
| usePlaybackQueue callback recreation | MEDIUM | Performance | #2137 |
| Zero test coverage for hooks | MEDIUM | Test Coverage | #2138 |
| 6 components exceed 300-line guideline | LOW | Component Quality | #2139 |

Additional frontend issues from other audits: #2088, #2098, #2100, #2101, #2104, #2111, #2113, #2115-#2118, #2148, #2162.

---

## Dimension Checklists (Incremental from Prior Audit)

### D1: Component Quality (NEW findings)
- [x] React.memo — TrackRow and list items not memoized (F2-H01)
- [x] Imperative DOM — PlaybackControls bypasses React (F2-M01)
- [x] Key usage — Index keys on dynamic lists (F2-M02)

### D2: Redux State (NEW findings)
- [x] Middleware — stale state read in NEXT/PREVIOUS (F2-M04)

### D3: Hook Correctness (NEW findings)
- [x] Callback stability — useOptimisticUpdate unstable execute (F2-M03)

### D5: Design System (NEW findings)
- [x] !important — CSS specificity conflicts in 2 components (F2-M05)

### D7: Performance (NEW findings)
- [x] Virtualization — TrackList renders all tracks to DOM (F2-H02)
- [x] Unused dependency — @tanstack/react-virtual not imported (F2-L01)

---

## Prioritized Fix Order

1. **F2-H01** — Wrap TrackRow in React.memo. Highest impact: eliminates O(n) re-renders on every state change. ~30min.
2. **F2-H02** — Integrate @tanstack/react-virtual in TrackList. Prevents DOM bloat for large libraries. ~2hr.
3. **F2-M04** — Combine NEXT/PREVIOUS dispatches into atomic reducer action. Prevents wrong track during shuffle. ~30min.
4. **F2-M03** — Refactor useOptimisticUpdate to use stateRef pattern. Prevents callback instability. ~30min.
5. **F2-M01** — Replace imperative DOM mutations with CSS :hover or React state. ~1hr.
6. **F2-M02** — Replace index keys with stable identifiers. ~15min.
7. **F2-M05** — Resolve CSS specificity without !important. ~30min.
8. **F2-L01** — Either use or remove @tanstack/react-virtual. ~5min (if combined with F2-H02).

---

## Cross-Cutting Recommendations

### 1. Component Memoization Policy
Establish a policy: all list item components MUST use `React.memo` with custom comparators. Add an ESLint rule (e.g., `react/display-name` + custom rule) to flag unmemoized components receiving > 3 props.

### 2. Virtualization Standard
Since `@tanstack/react-virtual` is already installed, create a shared `VirtualizedList` wrapper component that all list views (tracks, albums, artists, queue) use. This addresses F2-H02 and provides a consistent scrolling UX.

### 3. Declarative Styling
Replace all imperative `e.currentTarget.style.*` mutations with either CSS pseudo-classes (`:hover`, `:focus`) or a shared `useHoverState()` hook. This addresses F2-M01 and improves testability.

### 4. Atomic Redux Updates
When a message handler needs to update multiple slices, combine into a single reducer action (e.g., `nextTrackAndSetCurrent`) or use Redux `batch()`. This addresses F2-M04 and prevents transient state inconsistencies.
