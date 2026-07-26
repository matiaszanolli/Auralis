# Frontend Audit — 2026-07-25

**Scope**: `auralis-web/frontend/src/` — components, hooks, contexts, Redux store, services/API clients, types, design system, tests, config.
**Method**: Fresh 9-dimension audit (Component Quality, Redux State, Hook Correctness, Type Safety, Design System, API Client, Performance, Accessibility, Test Coverage), each run as an independent deep-read pass. No prior audit report was used as a source of findings.
**Baseline**: `git HEAD` = `54d055df` (168 commits since the 2026-07-12 frontend audit, including the desktop UI theme unification `f2143dd7`, the WebSocket subscription consolidation onto `WebSocketContext`, and several dead-component deletions).
**Dedup**: 300 most recent GitHub issues + `docs/audits/` + `.claude/issues/`.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 19 |
| LOW | 20 |
| **Total (new)** | **43** |

Plus 2 findings confirmed still-present but already tracked as OPEN issues (#4428, #4430) — reported here as context only, not counted as new.

### Key themes

1. **The theme unification did not land.** Commit `f2143dd7` introduced a semantic token contract (`themeVars`/`SemanticTheme`) and migrated the app *chrome* (top bar, sidebar, player frame, shared dialogs). It did not reach the application *body*. Only 20 production files import `themeVars`; 149 still read the raw, dark-only `tokens.colors.text.*`/`tokens.colors.bg.*`/`tokens.glass.*` primitives. This is not cosmetic debt — computed WCAG contrast on core, always-visible surfaces (artist list, every media card) falls to **1.05:1 and 1.74:1** in light mode. Both HIGH design-system findings are user-visible breakage of a feature that shipped three days ago.

2. **Accessibility gaps are concentrated in un-migrated components.** The two HIGH a11y findings (queue reorder is DnD-only; artist-page album cards have zero keyboard support) share a root cause with theme drift: components that were never migrated to the unified `MediaCard`/shared primitives retained their old, inaccessible implementations while their migrated siblings are correct.

3. **Dead code is the single largest maintenance liability.** Independently, seven of the nine dimensions each surfaced dead code in their own area: ~4.6k lines of unreachable enhancement components, the entire `performance/` toolkit, 11 dead REST/fingerprint types, dead `useQuery`/`useMutation`/fingerprint-cache hooks, a dead skip path in `queueSlice`, a dead telemetry sink, and a dead duplicate mock-fixture module. Several of these carry passing tests, manufacturing false coverage confidence.

4. **Nothing gates the frontend on tests.** The only frontend CI workflow is a type-check. The 85/85/80/85% coverage thresholds in `vitest.config.ts` are never invoked by anything, which is the structural reason the known ~138-spec failure baseline could accumulate.

5. **The mature layers really are mature.** Hooks, WebSocket transport, selector memoization, virtualization, image lazy-loading, and error boundaries were each investigated hard and largely came back clean. The audit's own headline performance hypothesis (WS consolidation causing whole-tree re-renders) was **disproven** — `WebSocketContext` routes to typed per-type subscriber sets with a properly memoized context value. Production TypeScript compiles with **zero** errors (208 remaining tsc errors are all in test files, down from the historical 332 baseline).

### Most impactful issues

- **FE-D1** — light mode renders invisible text across the library grid, artist list, and every media card.
- **FE-Y1 / FE-Y2** — two core flows (queue reordering, artist → album navigation) are completely unusable without a mouse.
- **FE-Q2** — no CI job runs the test suite, so every finding in this report could have landed silently and the next one will too.

---

## HIGH Findings

### FE-D1: Semantic theme contract does not reach the library/media/enhancement component tree — light mode text is unreadable
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Styles/ArtistList.styles.ts:79-98`, `auralis-web/frontend/src/components/shared/MediaCard/MediaCardInfo.tsx:56-87`, and ~149 other production files (see Siblings)
- **Status**: NEW
- **Description**: The new semantic contract (`auralis-web/frontend/src/theme/semanticTheme.ts`, consumed via `themeVars`) resolves `textPrimary`/`surfacePrimary`/etc. per theme mode. Only 20 production files import `themeVars`. 149 production files instead read the **raw, dark-only** primitive tokens directly — `tokens.colors.text.primary` is hardcoded to `rgba(255, 255, 255, 0.95)` in `auralis-web/frontend/src/design-system/tokens/colors.ts:100` with no light-mode variant. These components render near-white text regardless of `ThemeContext` mode. `ArtistName`/`ArtistInfo` set `color: tokens.colors.text.primary` unconditionally; in light mode the canvas is `tokens.colors.lightMode.background.primary = '#F8F9FD'`. `MediaCardInfo.tsx` (used by every album/track/playlist card grid) has the identical pattern over `tokens.glass.subtle.background`, a 25%-opacity tint that composites to a pale card in light mode.
- **Evidence**:
  ```ts
  // ArtistList.styles.ts:79-87
  export const ArtistName = styled(Typography)({
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,   // rgba(255,255,255,0.95) — never varies by theme
  });
  ```
  Computed WCAG contrast (relative-luminance, alpha-composited against the actual light-mode backgrounds these components render on):
  - `ArtistName`/`ArtistInfo` vs. light canvas `#F8F9FD`: **≈1.05:1** (AA requires 4.5:1)
  - `MediaCardInfo` primary caption vs. its own light-composited glass card: **≈1.74:1**

  Both fail even the 3:1 large-text floor. Corroborating blind spot: `auralis-web/frontend/src/components/shared/MediaCard/__tests__/MediaCardInfo.contrast.test.ts` hardcodes `CARD_BG = '#1A2338'` (dark-mode surface only) and asserts AA only against that color. No light-mode contrast test exists anywhere in the suite, so this regression class is structurally untested.
- **Impact**: Any user who toggles light mode sees the Artists tab and every media/track/playlist card render with invisible or near-invisible text — user-facing breakage of the just-landed theme feature on core, always-visible surfaces.
- **Siblings**: Same direct-primitive-token pattern (non-exhaustive, from the 149-file sweep): `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts`, the Avatar / Typography / Grid / Tabs / FormFields / ArtistDetail / Button style modules under `auralis-web/frontend/src/components/library/Styles/`, the ArtistHeader / ArtistDetailHeader / AlbumDetailView / AlbumMetadata components under `auralis-web/frontend/src/components/library/Details/`, `auralis-web/frontend/src/components/enhancement/`, `auralis-web/frontend/src/components/features/discovery/`, `auralis-web/frontend/src/components/shared/CacheManagementPanel/`, `auralis-web/frontend/src/components/settings/`, `auralis-web/frontend/src/components/playlist/`, `auralis-web/frontend/src/components/player/` (`TrackInfo`, `TimeDisplay`, `VolumeControl`, `ProgressBar.styles`). Re-running the theme doc's own heuristics today gives 201 hex/rgb files and 149 raw-token files against its stated 206/164 baseline — near-zero progress on its own follow-up items 1-3.
- **Related**: FE-D2 (same contract, different failure mode), FE-D3 (three competing color APIs is why this is easy to get wrong), FE-Y4 (a second, dark-mode-specific contrast class).
- **Suggested Fix**: Prioritize migrating `MediaCard`/`MediaCardInfo` and `library/Styles/*` (highest-traffic, always visible) to `themeVars.textPrimary`/`themeVars.surfacePrimary` per the doc's own follow-up order. Parametrize `MediaCardInfo.contrast.test.ts`'s `CARD_BG` over both themes so this class is caught by CI rather than manual QA.

---

### FE-D2: ShuffleModeSelector hover/focus state reads undefined CSS custom properties — permanently dark, unreadable in light mode
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css:38-44,86-93`
- **Status**: NEW
- **Description**: `.modeButton:hover` and `.tooltip` set `background-color: var(--bg-tertiary, #151D2F)`. `--bg-tertiary` is never produced anywhere — `getSemanticCssVariables()` (`auralis-web/frontend/src/theme/semanticTheme.ts:169-179`) only aliases `--bg-primary/-secondary/-surface/-hover/-glass` and `--text-primary/-secondary/-disabled`; `auralis-web/frontend/src/index.css`'s `:root` never defines it. A repo-wide grep for a `--bg-tertiary:` producer returns zero matches. Same for `--accent-primary`, `--accent-dark`, `--text-primary-full`, also referenced with hardcoded fallbacks in this file. Because the custom property is always unset, the CSS fallback is what renders — in both themes, unresponsive to `ThemeContext`.
- **Evidence**:
  ```css
  /* ShuffleModeSelector.module.css:38-44 */
  .modeButton:hover:not(:disabled) {
    background-color: var(--bg-tertiary, #151D2F);   /* never defined -> always #151D2F */
    border-color: var(--accent-primary, #7366F0);
  }
  ```
  The base `color: var(--text-primary, ...)` *is* correctly aliased and does react to theme — in light mode it resolves to `tokens.colors.lightMode.text.primary = '#1A1F3A'` (dark navy). On hover in light mode: dark-navy text on a dark-navy background, **contrast ≈1:1**.
- **Impact**: Hovering or tab-focusing a shuffle-mode button in light mode makes its label disappear, while every surrounding control in the same panel is correctly light-themed. Small blast radius (one component) but an unambiguous repro of a component that migrated only half its states.
- **Siblings**: None — `--bg-tertiary` is referenced only here (verified repo-wide).
- **Related**: FE-D1 (systemic version of the same gap), #4463 (tracks the duplicated `#7366f0` fallback value, but not the fact that the variable it "falls back" from is never produced — that failure mode is new here).
- **Suggested Fix**: Rewrite this stylesheet to consume `themeVars.surfaceOverlay`/`themeVars.accent`/`themeVars.accentHover`/`themeVars.textStrong` directly, per the theme doc's "no new component-local palettes" rule (preferred over adding four more CSS aliases).

---

### FE-Y1: Queue reordering is drag-and-drop only — no keyboard alternative
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueueTrackItem.tsx:62-74`, `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:148-178`
- **Status**: NEW
- **Description**: The playback queue's only reorder mechanism is native HTML5 drag-and-drop (`draggable`, `onDragStart`/`onDragOver`/`onDragEnd`) wired in `QueueTrackItem`. The row's `onKeyDown` implements only Delete/Backspace for removal; there is no keyboard path to `reorderTrack(fromIndex, toIndex)` (`auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:107`), which is invoked exclusively from `handleDragEnd`. No "Move up"/"Move down" context-menu action or shortcut exists anywhere in the queue panel or its context menu.
- **Evidence**:
  ```tsx
  // QueueTrackItem.tsx
  onKeyDown={(e) => {
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      if (!disabled) onRemove(index);
    }
  }}
  ...
  draggable
  onDragStart={() => onDragStart(index)}
  onDragEnd={onDragEnd}
  onDragOver={(e) => { e.preventDefault(); onDragOver(index); }}
  ```
- **Impact**: Keyboard-only and screen-reader users can view and remove queue tracks but cannot reorder them at all — a core queue-management flow is completely unusable without a pointer.
- **Siblings**: None — the only `draggable` usage in `components/` (verified repo-wide).
- **Related**: #4428 / FE-P1 (the same component's memoization and re-render behavior).
- **Suggested Fix**: Handle `Alt+ArrowUp`/`Alt+ArrowDown` in `QueueTrackItem`'s `onKeyDown` to call the existing `reorderTrack`, or add explicit "Move up"/"Move down" buttons in the row's `showActions` area.

---

### FE-Y2: Album cards in the Artist Detail "Albums" tab have zero keyboard support
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Styles/ArtistDetail.styles.ts:20-33`, `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:90-105`
- **Status**: NEW
- **Description**: `AlbumsTab.tsx` (rendered live inside `auralis-web/frontend/src/components/library/Details/ArtistDetailTabs.tsx` as the artist page's "Albums" tab) imports a local `AlbumCard = styled(Paper)` from `ArtistDetail.styles.ts` and gives it `onClick` directly with `cursor: 'pointer'` — but no `role`, `tabIndex`, or `onKeyDown`. This is a different, un-migrated component from the unified `auralis-web/frontend/src/components/album/AlbumCard/AlbumCard.tsx`, which delegates to `MediaCard` and correctly implements `role="button"`, `tabIndex={0}`, Enter/Space `onKeyDown`, and `aria-label`. The main library Albums grid, `CozyAlbumGrid`, `EraSection`, and `RecentlyTouchedSection` all use the accessible unified card; only this tab uses the old one.
- **Evidence**:
  ```tsx
  // ArtistDetail.styles.ts
  export const AlbumCard = styled(Paper)({ ..., cursor: 'pointer', ... });

  // AlbumsTab.tsx
  <AlbumCard onClick={() => onAlbumClick(album.id)}>
    <AlbumArt albumId={album.id} size="100%" borderRadius={0} />
  </AlbumCard>
  ```
  Compare the accessible sibling used everywhere else:
  ```tsx
  // MediaCard.tsx
  <Card tabIndex={0} role="button" onClick={props.onClick}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { ... props.onClick?.(); } }}
        aria-label={...}>
  ```
- **Impact**: A keyboard user on an artist's page cannot Tab to or activate any album card — artist → album navigation is completely unusable without a mouse, even though the equivalent flow from the main library view works correctly.
- **Siblings**: Single call site; the styled `AlbumCard` in `ArtistDetail.styles.ts` has no other consumers.
- **Related**: FE-C1 (same "un-migrated duplicate component" class), FE-D1 (`ArtistDetail.styles.ts` is also in the un-themed 149).
- **Suggested Fix**: Replace the local `styled(Paper)` `AlbumCard` in `AlbumsTab.tsx` with the unified `AlbumCard`/`MediaCard`, which also removes a duplicate implementation per the "no variants" principle.

---

## MEDIUM Findings

### FE-C1: Two entire component subtrees (~4.6k lines, 45+ files) are dead — orphaned "no-variants" duplicates never reached from the render tree
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/enhancement/` (10 files, 2135 lines), `auralis-web/frontend/src/components/enhancement-pane/` (32 files, 2313 lines), `auralis-web/frontend/src/components/library/TrackList.tsx:1-388`, `auralis-web/frontend/src/components/library/Items/tracks/DraggableTrackRow.tsx:1-122`
- **Status**: NEW (distinct from #4488, which only flags `EnhancementInspectionLayer/*` as untested — it does not note the component has zero live callers)
- **Description**: Traced the full render tree from `index.tsx` → `App.tsx` → `ComfortableApp.tsx` → `CozyLibraryView.tsx`/`Player.tsx`. Neither `components/enhancement/` (`PlayerEnhancementPanel`, `EnhancedPlaybackControls`, `EnhancementPane`, `EnhancementIdentityLayer`, `EnhancementInspectionLayer/*`, `StreamingErrorBoundary`/`StreamingErrorDisplay`/`StreamingErrorBoundaryWrapper`, `StreamingProgressBar`) nor the parallel `components/enhancement-pane/` (`AppEnhancementPane`, `Collapsed`/`Expanded` views, `sections/*`) is imported by anything outside their own barrels and each other. `ComfortableApp.tsx:328` documents the replacement: `{/* Right pane - AlbumCharacterPane replaces EnhancementPane globally */}`. `AppContainer.tsx:60` references `<AppEnhancementPane />` only inside a stale JSDoc `@example`. Separately, `library/TrackList.tsx` (superseded by `library/Views/TrackListView.tsx`) and `DraggableTrackRow.tsx` (exported from three barrels) have zero non-test, non-barrel importers.
- **Evidence**:
  ```
  $ grep -rln "PlayerEnhancementPanel\|EnhancementPane\b\|AppEnhancementPane\|EnhancedPlaybackControls" \
      --include="*.tsx" src | grep -v __tests__ | grep -v "components/enhancement"
  (no output)
  ```
- **Impact**: No user-facing breakage, but real maintenance cost: these files were still mechanically touched by unrelated repo-wide refactors (the `React.FC` migration across 245 files, TS-error passes, design-token migrations) without anyone noticing they are unreachable. `TrackList.tsx` and the `enhancement/` cluster retain their own passing test suites, manufacturing false confidence that these paths are covered and working when they are never invoked.
- **Siblings**: `auralis-web/frontend/src/components/shared/CacheHealthWidget.tsx` (356 lines), `auralis-web/frontend/src/components/shared/CacheHealthMonitor.tsx` (372 lines), `auralis-web/frontend/src/components/shared/CacheManagementPanel/CacheManagementPanel.tsx`, `auralis-web/frontend/src/components/shared/HealthStatusIndicator.tsx` — four components forming a "cache health" cluster, all dead, none wired into Settings.
- **Related**: FE-C2 (5 of the 10 oversized components are in this dead set), FE-D4 and FE-Y4 (several of their cited locations are inside these dead trees), FE-P2, FE-T2, FE-T5, FE-A5, FE-A7, FE-R5, FE-H3, FE-Q3 (the broader dead-code theme).
- **Suggested Fix**: Delete both directories (and their tests) in favor of the live `AlbumCharacterPane` path; delete `library/TrackList.tsx` and `DraggableTrackRow.tsx` in favor of `TrackListView`/`QueueTrackItem`; pick one of the three cache-health widgets and wire it into `SettingsDialog`, or delete all three.

---

### FE-R1: `player.currentTrack` and `queue.tracks[currentIndex]` are duplicated track records that diverge on a duration-only sync
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:134-150`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:134-136`, `auralis-web/frontend/src/store/selectors/queue.ts:27-36`
- **Status**: NEW
- **Description**: `PlayerTrack` and `QueueTrack` are structurally identical (`auralis-web/frontend/src/types/domain.ts:48-49`, both `Pick<Track, 'id'|'title'|'artist'|'album'|'duration'|'artworkUrl'>`), and the app keeps two independent copies of the current track — `player.currentTrack` and `queue.tracks[queue.currentIndex]`. `setDuration`'s reducer patches `state.currentTrack.duration` to keep that copy in sync (comment cites #2774/#4191) but cannot reach `queue.tracks` (different slice). `usePlayerStateSync` dispatches `setDuration` gated only on `'duration' in state`, independently of the `if (state.queue && Array.isArray(state.queue))` block that refreshes `queue.tracks`. A `player_state` message carrying a duration correction without a fresh queue array leaves the two copies divergent.
- **Evidence**:
  ```ts
  // playerSlice.ts setDuration — only currentTrack is patched
  if (state.currentTrack) { state.currentTrack.duration = action.payload; }
  ```
  ```ts
  // usePlayerStateSync.ts — duration and queue are independently gated
  if ('duration' in state && typeof state.duration === 'number' && Number.isFinite(state.duration)) {
    dispatch(setDuration(state.duration));   // currentTrack copy updated
  }
  ...
  if (state.queue && Array.isArray(state.queue)) {   // separate condition; may not fire
    dispatch(setQueue(tracks));
  }
  ```
- **Impact**: `selectCurrentQueueTrack`/`selectRemainingTime`/`selectTotalQueueTime` (queue "time remaining" and per-track durations) keep showing the pre-correction value while the progress bar shows the corrected one — a visibly diverging duplicate of the same fact.
- **Siblings**: Same risk for any `Track` field that can change post-hoc without a queue refresh in the same message (e.g. `artworkUrl`).
- **Suggested Fix**: Normalize (store tracks once in `queue.tracks`, keep `player.currentTrackId` as a pointer), or have `usePlayerStateSync` patch `queue.tracks[currentIndex].duration` alongside `setDuration`.

---

### FE-R2: Discrete WebSocket player events have no ordering/staleness guard, unlike the periodic `player_state` snapshot
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:192-241` (vs. the `lastSeenSeqRef` guard at `:73-100`)
- **Status**: NEW
- **Description**: The periodic `player_state` handler tracks `lastSeenSeqRef` and drops snapshots whose `seq` regresses, with an explicit comment that "the backend broadcasts player_state outside its update lock, so concurrent update_state() calls can deliver snapshots out of order." The discrete low-latency events added for #4144 (`track_changed`, `playback_started/resumed/paused/stopped`, `volume_changed`) carry no `seq`/timestamp and are applied unconditionally. `playerSlice.ts` itself independently added trackId guards to `updateStreamingProgress`/`completeStreaming`/`setStreamingError` specifically to "drop late updates from a superseded track after a rapid skip (#4434)" — the same race class the discrete `track_changed` handler is unprotected against.
- **Evidence**:
  ```ts
  const unsubscribeTrackChanged = subscribe('track_changed', (message) => {
    const data = (message as { data?: { action?: string; track_index?: number } }).data;
    if (!data || typeof data.track_index !== 'number' || !Number.isInteger(data.track_index)) return;
    const index = data.track_index;
    const tracks = store.getState().queue.tracks;
    if (index >= 0 && index < tracks.length) {
      dispatch(setCurrentIndex(index));      // no ordering check
      dispatch(setCurrentTrack(tracks[index]));
    }
  });
  ```
- **Impact**: A rapid skip-skip-skip burst can, if the backend's two async `next_track()`/`previous_track()` handlers (`auralis-web/backend/services/navigation_service.py:74-96,120-136`, each doing a synchronous index mutation followed by an `await ...broadcast(...)`) interleave, apply an older index after a newer one — "Now Playing" shows the wrong track until the next authoritative snapshot corrects it (~1s per the file's own docs).
- **Suggested Fix**: Include `seq` on the discrete events and reuse `lastSeenSeqRef`, or have the backend include the track id so the frontend can apply the same `trackId`-based staleness guard already used in `playerSlice.ts` for #4434.

---

### FE-R3: `useQueueMutations` inconsistently applies optimistic Redux updates — half the mutations wait on the WebSocket round-trip
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:84-273`
- **Status**: NEW
- **Description**: The hook's docblock claims "optimistic Redux updates and rollback-on-error" for all queue mutations. `setQueue`, `toggleShuffle`, `setRepeatMode`, and `clearQueue` honor that. `addTrack`, `removeTrack`, `reorderTrack`, and `reorderQueue` do neither — they only call the REST endpoint and rely on the `queue_changed` broadcast (`auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:47-53`) to update Redux afterward.
- **Evidence**:
  ```ts
  // setQueue — optimistic + rollback
  dispatch(reduxSetQueue(tracks));
  try { await post('/api/player/queue', ...); }
  catch (err) { dispatch(reduxSetQueue(previousTracks)); ... }

  // reorderTrack — no Redux dispatch at all
  const reorderTrack = useCallback(async (fromIndex, toIndex) => {
    try { await put('/api/player/queue/reorder', { from_index: fromIndex, to_index: toIndex }); }
    catch (err) { ... }   // nothing to roll back — nothing was applied
  }, [put]);
  ```
- **Impact**: `QueuePanel.tsx:148-156` wires drag-and-drop reorder directly to `reorderTrack`, so a dropped track shows no reordering until the PUT succeeds and `queue_changed` round-trips — on a slow tick the item visually snaps back, reading as "the drag failed" while the request is in flight. Same for remove-track clicks.
- **Suggested Fix**: Apply the optimistic-dispatch + ref-based rollback pattern already used by `setQueue`/`clearQueue` to the other four, or narrow the docblock's claim and give the affected UI its own local pending/dragging state.

---

### FE-D3: Three coexisting color-source APIs — raw tokens, legacy `themeConfig` colors, and the new semantic layer
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:27-68,507`, `auralis-web/frontend/src/theme/semanticTheme.ts:1-180`, `auralis-web/frontend/src/design-system/tokens/colors.ts`
- **Status**: NEW
- **Description**: `useTheme()` (`auralis-web/frontend/src/contexts/ThemeContext.tsx:10-16,58-64`) still exposes `colors` and `glassEffects` from `themeConfig.ts`, explicitly re-exported "for backward compatibility" (`themeConfig.ts:507`). That is a second, independent color API alongside the new `themeVars`/`SemanticTheme` contract — and a third exists as the raw `tokens.colors.*` primitives consumed directly by ~149 files (FE-D1). Per the project's "no variants" rule, three live color-resolution paths for the same visual concept is exactly what the rule exists to prevent; the theme doc lists removing this as unfinished follow-up work (item 6).
- **Evidence**:
  ```ts
  // theme/themeConfig.ts:506-508
  export const auralisTheme = createAuralisTheme('dark');
  export { darkColors as colors }; // For backward compatibility
  ```
- **Impact**: Low immediate breakage risk (only `auralis-web/frontend/src/components/shared/ui/ThemeToggle.tsx` still destructures `colors` from `useTheme()`). The real cost is discoverability: a new component author has three equally plausible "correct" ways to get a color, and only the doc — not the type system — says which is canonical. This is the enabling condition for FE-D1/FE-D2.
- **Siblings**: The compatibility CSS-variable aliases in `semanticTheme.ts:169-179` (`--bg-primary`, `--text-primary`, etc.) are the same category of debt and have **zero** production consumers — deletable immediately with no migration risk.
- **Suggested Fix**: Migrate `ThemeToggle.tsx`'s single remaining `colors` usage to `themeVars`, then delete the `darkColors`/`lightColors`/`glassEffects` re-exports and the dead CSS alias block.

---

### FE-T1: `cache_cleared` WebSocket broadcast has no frontend type and is silently dropped
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/backend/routers/cache_streamlined.py:160-164`, `auralis-web/frontend/src/types/ws/registry.ts:66-156`, `auralis-web/frontend/src/contexts/WebSocketContext.tsx:157-176`
- **Status**: NEW
- **Description**: `POST /api/cache/clear` broadcasts `{"type": "cache_cleared", ...}` over the same shared `ConnectionManager` used for every other domain event. The backend comment even says the envelope was shaped "so the frontend dispatcher does not classify it as unknown" — but the frontend never defines this message. It is absent from `WebSocketMessageType`, `AnyWebSocketMessage`, and `ALL_MESSAGE_TYPES`; the string `cache_cleared` appears nowhere under `src/` (verified repo-wide). `WebSocketContext.dispatchMessage` looks up handlers by type in a `Map`; an unregistered type has no subscribers and is dropped without warning.
- **Evidence**:
  ```python
  # auralis-web/backend/routers/cache_streamlined.py:160-164
  if broadcast_manager:
      await broadcast_manager.broadcast({
          "type": "cache_cleared",
          "data": {"message": "All caches cleared"},
      })
  ```
  ```ts
  // types/ws/registry.ts — no 'cache_cleared' in the union
  export type WebSocketMessageType =
    | PlayerMessageType | QueueMessageType | LibraryMessageType
    | StreamingMessageType | EnhancementMessageType | 'error';
  ```
- **Impact**: Cache-stats/health UI cannot react live to a cache clear and shows stale "cached" state until navigated away and back. The `_AssertExhaustive` check in `registry.ts` only guards types already imported into the file — it cannot catch a backend event never modeled on the frontend, so this gap class is invisible to the type system.
- **Siblings**: Checked `auralis-web/backend/routers/metadata.py`'s two broadcasts (`metadata_updated`, `metadata_batch_updated`) — both correctly represented in `auralis-web/frontend/src/types/ws/library.ts`. `cache_cleared` is the only orphaned broadcast type.
- **Suggested Fix**: Add a `CacheClearedMessage` type, register it in `WebSocketMessageType`/`AnyWebSocketMessage`/`ALL_MESSAGE_TYPES`, and subscribe the cache-stats UI via `useWebSocketMessages(['cache_cleared'], …)`.

---

### FE-T2: Several REST request/response types in `types/api.ts` are dead AND stale — landmines for the next consumer
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/api.ts:54-77,160-164,228-236,335-346`
- **Status**: NEW
- **Description**: `PlayerPlayRequest`, `PlayerQueueAddRequest`, `PlayerQueueRemoveRequest`, `PlayerQueueReorderRequest`, `EnhancementSettingsRequest`, `ArtworkUpdateRequest/Response`, `StreamingUrlRequest/Response` have zero real importers (verified per-symbol, not by substring). Several have also drifted from the real backend contract:
  - `PlayerQueueAddRequest { track_path: string }` vs. the real `AddTrackToQueueRequest { track_id: int, position: int | None }` (`auralis-web/backend/routers/player.py:69-72`) — different field name *and* type.
  - `PlayerQueueRemoveRequest { index: number }` implies a JSON body; the real endpoint takes `index` as a **query parameter** (`routers/player.py:617`).
  - `PlayerQueueReorderRequest` coincidentally matches `MoveQueueTrackRequest`, but the backend also has a same-purpose `ReorderQueueRequest { new_order: list[int] }` with a different shape (`routers/player.py:58-65`).
  - `StreamingUrlRequest/Response` model an endpoint that was never built — there is no streaming router under `auralis-web/backend/routers/`.
- **Evidence**:
  ```ts
  // types/api.ts:66-77 (dead, and wrong if resurrected)
  export interface PlayerQueueAddRequest { track_path: string; }
  export interface PlayerQueueRemoveRequest { index: number; }
  ```
  ```python
  # auralis-web/backend/routers/player.py:69-72 (actual contract)
  class AddTrackToQueueRequest(BaseModel):
      track_id: int
      position: int | None = None
  ```
- **Impact**: Zero today. The risk is prospective and specific: these names are exactly what a developer implementing a new queue-add call site would reach for, and using them compiles cleanly while sending `{track_path: "..."}` to an endpoint expecting `{track_id: 123}` — a 422 to debug with no compiler help. This mirrors the cleanup already done once under #4372 for `LibraryScanRequest`/`MetadataUpdateRequest`/`SimilarTracksRequest`; these nine were missed.
- **Related**: FE-T5 (same family), FE-T3 (the reason type drift goes unnoticed at runtime).
- **Suggested Fix**: Delete the confirmed-dead interfaces, same treatment as #4372.

---

### FE-T3: `apiRequest<T>()` returns `response.json()` directly — every "typed" API response is unvalidated `any` wearing a label
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts:112-147`
- **Status**: NEW
- **Description**: `apiRequest<T>()` is the single low-level fetch wrapper behind `get`/`post`/`put`/`patch`/`del`, which back nearly every service and hook. The success path is `return response.json()` — `Response.json()` is `Promise<any>` per the DOM lib types, and TypeScript silently narrows it to the caller's `T` with no runtime check anywhere in the chain. No schema-validation library (zod, io-ts, ajv) or manual guard exists at this boundary.
- **Evidence**:
  ```ts
  // utils/apiRequest.ts:140-147
  if (response.ok) {
    if (response.status === 204) { return undefined as T; }
    return response.json();  // Promise<any> silently becomes Promise<T>
  }
  ```
- **Impact**: Every interface in `types/api.ts`/`types/domain.ts`/`api/transformers/types.ts` is a compile-time-only contract. If the backend renames a field, drops one, or sends `null` where the type says `string`, nothing catches it until a component crashes or renders "undefined". This is precisely the class the file's own comments show has bitten before (#3593 hit_rate drift, #3976 HealthResponse mismatch, #4440 bare-vs-enveloped cache payloads) — each caught only after visible breakage, the expected failure mode of an unvalidated boundary.
- **Siblings**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts` has the same `response.json()` shape with an added `isSuccessResponse`/`isErrorResponse` predicate layer — a genuine partial mitigation that checks the envelope but not the shape of `data`.
- **Related**: FE-A1 and FE-A2 (concrete instances of drift this boundary cannot catch), FE-T2/FE-T5.
- **Suggested Fix**: Not a full runtime-schema rewrite (disproportionate for a localhost-only single-consumer app), but extend the existing `isCacheStatsShape`/`isCacheHealthShape` guards (already added for #4440) to the highest-traffic endpoints (tracks/albums/artists list, player state) so shape drift fails loud rather than silently.

---

### FE-H1: `useEnhancedPlayCommand` depends on the whole unmemoized `core` object, breaking `playEnhanced` identity stability and cascading into `Player.tsx`
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:58-145` (dep array at 144); root cause `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:481-506`; downstream `auralis-web/frontend/src/components/player/Player.tsx:95-208`
- **Status**: NEW
- **Description**: `useAudioStreamingCore` returns a plain object literal every render (no `useMemo`), which is exactly why every other consumer in this hook family (`useEnhancedSeek.ts:89`, `useEnhancedStreamStart.ts`) deliberately depends on individual `core.xxxRef` fields rather than the whole object — an established, commented pattern in the same file family. `useEnhancedPlayCommand.ts` is the one outlier: its dep array is `[wsContext, dispatch, core, currentTrackInfoRef, resetFingerprint]`. Since `core` is a new identity every render, `playEnhanced` is too. `Player.tsx` then includes `playEnhanced` in the deps of `handleNext` (118), `handlePrevious` (142), and `handlePlayPause` (168), so those three `useCallback`s are effectively unmemoized; `handleNext` is further a dependency of the auto-advance `useEffect` at line 208.
- **Evidence**:
  ```ts
  // useEnhancedPlayCommand.ts:144 — depends on the whole `core` object
  }, [wsContext, dispatch, core, currentTrackInfoRef, resetFingerprint]);

  // useEnhancedSeek.ts:89 — sibling hook correctly avoids this
  }, [wsContext, currentTrackInfoRef, setIsSeeking, core.playbackEngineRef, core.pcmBufferRef,
      core.streamingMetadataRef, core.pendingChunksRef, core.lastReceivedChunkIndexRef]);
  ```
- **Impact**: `playEnhanced`/`handleNext`/`handlePrevious`/`handlePlayPause` never have a stable identity, so any `React.memo`'d child of `Player.tsx` receiving them re-renders on every parent render, and any effect/memo keyed on them re-evaluates far more often than its dep array implies. Not currently causing incorrect playback (the auto-advance effect is separately guarded by `hasAutoAdvancedRef`), but it silently defeats the stability discipline this codebase enforces everywhere else in the same family — and it is a prerequisite blocker for the FE-P1 fix.
- **Siblings**: None elsewhere in the enhancement family — `useEnhancedSeek.ts` and `useEnhancedStreamStart.ts` both destructure individual `core.*Ref` fields.
- **Related**: FE-P1 (memoizing `Player.tsx`'s children is ineffective until these callback identities are stable).
- **Suggested Fix**: Wrap `useAudioStreamingCore`'s return in `useMemo`, or list the individual `core.*Ref` fields in `useEnhancedPlayCommand`'s dep array, matching `useEnhancedSeek`'s pattern.

---

### FE-H2: `useLibraryQuery`'s auto-fetch effect has no stale-response guard
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:267-320` (`executeQuery`), `:383-391` (auto-fetch effect)
- **Status**: NEW
- **Description**: The auto-fetch effect re-runs `executeQuery(0, false)` whenever `queryType`/`options.search`/`options.orderBy`/`options.limit`/`options.endpoint` change — e.g. every debounced keystroke via `useTracksQuery({ search })`. `executeQuery`'s only in-flight guard is `queryKeyRef.current === queryKey && isFetchingRef.current`, but `queryKey` derives from the endpoint URL, which differs for every distinct search string, so the guard never fires across a fast sequence of different searches. There is no `isActive`/generation-counter check before the `setData`/`setTotal`/`setOffset`/`setHasMore` calls after `await get(...)` — unlike `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:33-71` and `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:184-208`, which cite this exact race (#3925) and guard it.
- **Evidence**:
  ```ts
  // useLibraryQuery.ts:267-320 — no per-call staleness token
  const queryKey = `${queryType}:${url}:${targetOffset}`;
  if (queryKeyRef.current === queryKey && isFetchingRef.current) return; // only catches identical URL
  ...
  const response = await get<LibraryQueryResponse<T>>(url);
  setData(items); // no check that this is still the latest search term
  ```
  vs. the guarded sibling pattern already in the codebase:
  ```ts
  // useQueueFetch.ts:37-71
  let isActive = true;
  const response = await get(...);
  if (response && isActive) { dispatch(...); }
  return () => { isActive = false; };
  ```
- **Impact**: Typing into a debounced (300ms) search box can trigger overlapping requests; if the earlier one resolves last, results render for a search term no longer in the input. Low likelihood on a localhost backend, but a real unguarded race exactly matching a pattern already fixed twice elsewhere.
- **Siblings**: `useQueueFetch.ts`, `useQueueHistory.ts` (correct); `useLibraryQuery.ts` and its exports `useTracksQuery`/`useArtistsQuery` (unguarded).
- **Suggested Fix**: Add a per-effect `isActive` flag or a monotonic request-id ref (matching `useEnhancementControl.ts`'s `presetRequestIdRef` pattern for #4339) around the state setters, cleared in the effect's cleanup.

---

### FE-A1: `useLibraryQuery('tracks', ...)` bypasses the canonical transformer — snake_case fields leak as `undefined`
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:216-234`
- **Status**: NEW
- **Description**: `extractItemsFromResponse()` switches on query type. For `'albums'`/`'artists'` it runs the payload through the canonical transformers (both annotated "no inline variant (#4418)"). For `'tracks'` it does neither — a raw cast with zero field conversion. The backend's `GET /api/library/tracks` (`auralis-web/backend/routers/tracks.py:39-69`) serializes via `serialize_tracks()` → `DEFAULT_TRACK_FIELDS` (`auralis-web/backend/routers/serializers.py:18-38`), which is snake_case (`artwork_url`, `sample_rate`, `bit_depth`, `date_added`, `date_modified`, `album_id`). The `Track` domain type and `transformTrack()` expect the camelCase equivalents.
- **Evidence**:
  ```ts
  // hooks/library/useLibraryQuery.ts:216-234
  switch (qType) {
    case 'tracks':
      return ((response.tracks ?? response.items) as T[]) || [];
    case 'albums':
      // Canonical transformer is the single source of truth for snake→camel (#4418).
      return transformAlbums(...) as T[];
    case 'artists':
      return transformArtists(...) as T[];
  ```
  Confirmed by the test suite itself: `auralis-web/frontend/src/hooks/library/__tests__/useLibraryQuery.test.ts:1049-1087` has explicit album/artist snake→camel mapping tests but no track equivalent, and the track fixture uses only fields spelled identically in both cases — so the gap is invisible to the tests.
- **Impact**: `TrackList.tsx` (the only current consumer) renders only `title`/`artist`/`album`/`duration`, identical in both casings, so nothing visibly breaks today. But the hook's return type promises a fully populated `Track[]` and silently does not deliver — any new feature on `useTracksQuery` (artwork thumbnails, sort by date-added) reads `undefined` with no error, no warning, and passing type-checks.
- **Siblings**: None — `'albums'`/`'artists'` in the same switch already got this fix under #4418; `'tracks'` was left out.
- **Related**: FE-T3 (why this passes type-check), FE-A2 (why there are two transformers to forget).
- **Suggested Fix**: Add `case 'tracks': return transformTracks(response.tracks ?? response.items ?? []) as T[];` using the existing `auralis-web/frontend/src/api/transformers/trackTransformer.ts`, plus a test mirroring the album/artist mapping tests.

---

### FE-A2: Two competing, independently-maintained track transformers, both claiming to be "the" canonical mapping
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/api/transformers/trackTransformer.ts:19-53` vs. `auralis-web/frontend/src/types/domain.ts:409-424`
- **Status**: NEW
- **Description**: Two separate snake→camel track transforms, each with a docstring asserting singular ownership. `transformTrack()` → `Track` (includes `bitrate`, `sampleRate`, `bitDepth`, `format`, `loudness`, `crestFactor`, `centroid`, `dateAdded`, `dateModified`). `transformBackendTrack()` → a different type, `LibraryTrack` (includes `albumId`, `favorite`; drops all the audio-quality fields), with the docstring *"Single source of truth for backend→frontend track mapping."* Both are live against the same endpoint family: `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts` uses `transformBackendTrack`/`LibraryTrack`, while `useLibraryQuery.ts`/`useArtistDetailsData.ts` use `transformTrack`/`Track`.
- **Evidence**:
  ```ts
  // api/transformers/trackTransformer.ts:10-18
  /** Backend contract (snake_case): sample_rate, bit_depth, crest_factor, date_added, date_modified */
  export function transformTrack(apiTrack: TrackApiResponse): Track { ... }

  // types/domain.ts:405-409
  /** Single source of truth for backend→frontend track mapping. */
  export function transformBackendTrack(track: TrackApiResponse): LibraryTrack { ... }
  ```
- **Impact**: A backend payload change needs updating in two places; whoever fixes one and forgets the other reintroduces the FE-A1 leak in whichever hook they didn't touch. It also means the "same" track renders with different available fields depending which hook loaded it (`favorite` present via one path, absent via the other).
- **Siblings**: None beyond these two — `Album`/`Artist` each have exactly one transformer.
- **Suggested Fix**: Pick one canonical `Track` type and transformer (`api/transformers/` is more complete and better tested); migrate `useLibraryPagination.ts` off `LibraryTrack`, or explicitly document `LibraryTrack` as a deliberately reduced view and fix the misleading docstring.

---

### FE-A3: `createCrudService` provides no request-cancellation support — 5 services can't abort in-flight requests
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/serviceFactory.ts:55-142`
- **Status**: NEW
- **Description**: `createCrudService()`'s `list`/`getOne`/`create`/`update`/`delete`/`custom` call `get`/`post`/etc. from `apiRequest.ts` with no options object — even though `apiRequest()` supports a `signal` (`apiRequest.ts:42`) for exactly this purpose. None of the generated methods expose a way to pass one through, so every service built on the factory has no cancellation path: `playlistService.ts`, `queueService.ts`, `settingsService.ts`, `similarityService.ts`, `artworkService.ts`.
- **Evidence**:
  ```ts
  // utils/serviceFactory.ts:55-63
  async list(params?: P): Promise<T[]> {
    const endpoint = typeof endpoints.list === 'function' ? endpoints.list(params) : endpoints.list;
    return get(endpoint);   // no options/signal parameter possible
  },
  ```
- **Impact**: Components calling e.g. `playlistService.getPlaylists()` in a `useEffect` and unmounting before the response arrives cannot cancel the fetch. Mostly a wasted round-trip (no `setState` inside the service), but it is a structural inconsistency: `apiRequest()`, `useRestAPI`, `StandardizedAPIClient`, and most raw `fetch()` sites all wire up `AbortController`/`signal` deliberately — this factory layer is the one place that cannot.
- **Siblings**: All 5 services built on `createCrudService`.
- **Suggested Fix**: Thread an optional `{ signal?: AbortSignal }` through the generated methods to the underlying `get`/`post`/`put`/`del`, mirroring `apiRequest.ts`'s `RequestOptions`.

---

### FE-P1: Player's 10Hz playback-position tick re-renders unmemoized siblings on every tick
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:424-435`, `auralis-web/frontend/src/components/player/Player.tsx:56-71,312-321`, `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:14-17`
- **Status**: NEW
- **Description**: `useAudioStreamingCore` runs a `setInterval(..., 100)` while playing, calling `setCurrentTime` in **local hook state** at 10Hz to drive the transport UI. `Player` is a single non-memoized function component that renders `TrackDisplay`, `PlaybackControls`, `VolumeControl`, `BufferingIndicator`, `QueueControlBar`, and — always mounted, only hidden via CSS per the `#2541` comment — the entire `QueuePanel`. None of those files are wrapped in `React.memo` (verified: no `memo(` in any of them; only the innermost `QueueTrackItem` is memoized). So `Player`'s body re-executing every 100ms re-renders all of them, even though none of their props change.
- **Evidence**:
  ```tsx
  // useAudioStreamingCore.ts:424-435
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      const time = playbackEngineRef.current?.getCurrentPlaybackTime() || 0;
      setCurrentTime((prev) => (time === prev ? prev : time));
    }, 100);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Player.tsx:312-321 — QueuePanel always mounted, never memoized
  <Box id="queue-panel-region" sx={{ ..., display: queuePanelOpen ? undefined : 'none' }}>
    <QueuePanel collapsed={false} onToggleCollapse={() => setQueuePanelOpen(false)} />
  </Box>
  ```
  Note the inline `onToggleCollapse` arrow also gets a fresh identity every render, so adding `React.memo` to `QueuePanel` alone would not help until that prop is stabilized.
- **Impact**: While a track is playing (most of a session), `QueuePanel`'s full body re-executes 10×/second: re-invoking `usePlaybackQueue()`, re-running `useVirtualizer()`, and re-creating the JSX for visible rows (only the leaf `QueueTrackItem`s are protected from DOM re-render; the reconciliation above them still happens). Five other transport components pay the same cost. On a machine also running the Python DSP engine, this is continuous, avoidable CPU churn for the whole duration of playback.
- **Siblings**: The same pattern applies to `usePlayNormal` (same `useAudioStreamingCore`).
- **Related**: FE-H1 (unstable callback identities block the memo fix), #4428 (compounds — the queue key already defeats `QueueTrackItem`'s memo on reorder).
- **Suggested Fix**: Wrap `QueuePanel`, `TrackDisplay`, `PlaybackControls`, `VolumeControl`, `BufferingIndicator`, `QueueControlBar` in `React.memo`, and stabilize `onToggleCollapse` with `useCallback(() => setQueuePanelOpen(false), [])`. Fix FE-H1 first or the memoization is partially defeated.

---

### FE-Y3: Playlists section header advertises `role="button"` but is not keyboard-operable
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/playlist/PlaylistListHeader.tsx:48-53`
- **Status**: NEW
- **Description**: The sidebar's "Playlists" expand/collapse header renders `SectionHeader` (a `styled(Box)`, i.e. a plain `<div>`, from `auralis-web/frontend/src/components/playlist/PlaylistList.styles.ts:23-33`) with `role="button"`, `aria-label`, and `aria-expanded`, but no `tabIndex` and no `onKeyDown`. A `<div>` is not natively focusable, so it is skipped entirely by Tab; even if focus reached it, no key handler fires `onExpandToggle`. This is the only `role="button"` element in the tree missing both (verified repo-wide — every other instance pairs the role with `tabIndex` + `onKeyDown`).
- **Evidence**:
  ```tsx
  <SectionHeader
    onClick={onExpandToggle}
    role="button"
    aria-label={expanded ? 'Collapse playlists' : 'Expand playlists'}
    aria-expanded={expanded}
  >
  ```
- **Impact**: Keyboard users cannot reach or toggle the Playlists section — worse than an unlabeled div, because screen readers announce an interactive "button" that then does not respond to Enter/Space.
- **Siblings**: None found. (`auralis-web/frontend/src/components/library/Items/artists/ArtistListHeader.tsx`'s equivalent has no `onClick` at all and is purely presentational — unaffected.)
- **Suggested Fix**: Add `tabIndex={0}` and an `onKeyDown` firing `onExpandToggle` on Enter/Space (preventing default on Space), matching the pattern already in `ClearQueueDialog.tsx` and `MediaCard.tsx`.

---

### FE-Y4: `text.disabled` token used for normal-size text fails WCAG AA contrast in multiple places
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/design-system/tokens/colors.ts:110`; consumers below
- **Status**: NEW
- **Description**: `tokens.colors.text.disabled` is `rgba(255,255,255,0.40)`, calibrated per its own comment only for the "WCAG AA 3:1 large-text minimum" (≥18px regular / ≥14px bold). Against the app's actual dark surfaces (`bg.level1` `#101729` → `bg.level4` `#1F2940`) it measures **3.59–3.81:1**, failing the 4.5:1 normal-text requirement. The team already found and fixed this exact bug twice (comments cite #4182 and #4451, swapping to `text.metadata` at 60% white, ~6.2–7.0:1), but at least 8 more call sites still use it for small/normal text — three of which additionally multiply it by a CSS `opacity` on the same element, the identical "compounding" anti-pattern the #4451 comment calls out, pushing effective contrast to **~1.9–2.2:1**.
- **Evidence**:
  ```ts
  // colors.ts:106-110
  metadata: 'rgba(255, 255, 255, 0.60)',  // ≥60% for AA 4.5:1 against bg.level1 (#2803)
  disabled: 'rgba(255, 255, 255, 0.40)',  // ≥40% for AA 3:1 large-text minimum (#2803)
  ```
  Unfixed normal-size consumers: `auralis-web/frontend/src/components/playlist/AddToPlaylistMenu.tsx:79` (body2/14px), `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:41-46` (body2), `auralis-web/frontend/src/components/enhancement-pane/views/Expanded.tsx:158-166` (caption/xs), `auralis-web/frontend/src/components/shared/ContextMenu/PlaylistSection.tsx:46-53` (xs), `auralis-web/frontend/src/components/playlist/PlaylistList.styles.ts:157-162` (13px).
  Compounded with an extra `opacity`:
  ```ts
  // components/library/Items/tracks/TrackRow.styles.ts:214-221
  export const TrackDuration = styled(Typography)({
    color: tokens.colors.text.disabled,
    opacity: 0.5,   // effective alpha ~20% -> ~1.9:1
  });
  ```
  Also `auralis-web/frontend/src/components/enhancement-pane/container/AppEnhancementPaneStyles.ts:49-58` (`opacity: 0.6` → ~2.2:1) and `auralis-web/frontend/src/components/shared/ContextMenu/ContextMenu.styles.ts:37-39` (`opacity: 0.5` → ~1.9:1).
- **Impact**: Low-vision users cannot read these labels ("No playlists yet", "Add folders above to begin scanning", disabled context-menu items, track durations) against the dark UI; the compounded instances are near-invisible — matching the severity the team already flagged in #4451.
- **Siblings**: 8 call sites above (2 already correctly fixed and excluded: `MediaCardInfo.tsx`, the sidebar `SectionLabel`). Two of the 8 (`Expanded.tsx`, `AppEnhancementPaneStyles.ts`) are inside the dead trees in FE-C1 and would be resolved by deletion.
- **Related**: FE-D1 (light-mode contrast, distinct axis of the same problem class), FE-C1.
- **Suggested Fix**: Same remediation already applied twice — swap to `tokens.colors.text.metadata` wherever it labels normal/small text, and drop the extra `opacity` multiplier on `TrackDuration`, `PaneTitle`, and the `ContextMenu` disabled style since the token is already the intended faded treatment.

---

### FE-Y5: No automated accessibility testing anywhere in the frontend
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/a11y/` (only file: `focusManagement.ts`), `auralis-web/frontend/package.json`
- **Status**: NEW
- **Description**: A dedicated `a11y/` directory exists but contains only manual focus-management utilities. No `jest-axe`, `vitest-axe`, or `axe-core` dependency appears in `package.json`, and no test in the 513-component tree calls `toHaveNoViolations` or similar. There is zero automated regression coverage for missing ARIA, contrast, or focus-order problems.
- **Evidence**: `grep -rn "jest-axe\|vitest-axe\|axe-core\|toHaveNoViolations" auralis-web/frontend/src auralis-web/frontend/package.json` → no matches. `find src/a11y -type f` → only `focusManagement.ts`.
- **Impact**: Every accessibility regression — including FE-Y1/FE-Y2/FE-Y3 in this report — can land and ship silently. There is no CI gate that would catch a missing `aria-label`, a role/tabIndex mismatch, or a contrast regression in a future PR.
- **Related**: FE-Q2 (even if a11y tests existed, no CI job runs the suite), FE-D1 (the missing light-mode contrast test is the same blind spot).
- **Suggested Fix**: Add `vitest-axe` with a shared `expectNoA11yViolations(container)` helper, wired into the existing suites for the player transport controls, `QueuePanel`, and the dialog components as a starting set.

---

### FE-Q1: `useQueueSubscription`'s WebSocket→Redux dispatch logic has zero test coverage; the one place that touches it mocks it away
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts:38-72`
- **Status**: NEW
- **Description**: `useQueueSubscription` was extracted from `usePlaybackQueue` in #4292 specifically "to give the WS-subscription path its own focused, independently-testable home" (its own file header). No *useQueueSubscription.test.ts* was ever created. Its only consumer is tested in `auralis-web/frontend/src/hooks/player/__tests__/usePlaybackQueue.test.ts`, whose `beforeEach` does `vi.spyOn(useWebSocketModule, 'useWebSocketMessages').mockReturnValue(undefined as any)` — replacing the entire subscription mechanism with a no-op before the callback ever runs. The hook's real branching (mapping `queue_changed`/`queue_shuffled`/`repeat_mode_changed` to Redux actions, including a dual snake_case/camelCase field fallback) has never been exercised by any test.
- **Evidence**:
  ```ts
  // useQueueSubscription.ts:47-51 — untested branch logic
  case 'queue_changed': {
    const { data } = msg;
    if (data.tracks) dispatch(reduxSetQueue(data.tracks));
    if (data.current_index != null) dispatch(reduxSetCurrentIndex(data.current_index));
    else if (data.currentIndex != null) dispatch(reduxSetCurrentIndex(data.currentIndex));
    break;
  }
  ```
  ```ts
  // usePlaybackQueue.test.ts:76-79 — the only composer mocks the transport away
  vi.spyOn(useWebSocketModule, 'useWebSocketMessages').mockReturnValue(undefined as any);
  ```
- **Impact**: If a contract change breaks the field-name fallback, no test fails. Real-time queue sync (drag-reorder from another view, shuffle/repeat broadcasts) could silently stop updating Redux with no signal.
- **Siblings**: `useQueueFetch.ts` and `useQueueMutations.ts` (the other two hooks from the same #4292 split) ARE meaningfully exercised through `usePlaybackQueue.test.ts` — this is specific to the subscription hook.
- **Suggested Fix**: Add a *useQueueSubscription.test.ts* spec mirroring `useArtworkUpdates.test.ts`/`useScanProgress.test.ts` — mock `subscribe` to capture the callback, deliver synthetic messages in both casings, assert against a real in-memory `queueSlice` store.

---

### FE-Q2: No CI job runs the vitest suite; the coverage thresholds in `vitest.config.ts` are decorative
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/vitest.config.ts:96-103`, `.github/workflows/frontend-typecheck.yml:1-51`
- **Status**: NEW
- **Description**: `vitest.config.ts` declares `coverage.thresholds` of lines 85 / functions 85 / branches 80 / statements 85 — which would fail a `vitest run --coverage`. But the repo's only frontend CI workflow runs `pnpm run type-check:prod` and nothing else. There is no workflow, husky hook, or lint-staged config anywhere that invokes `pnpm test`, `test:run`, or `test:coverage` (verified: `grep -rn "vitest" .github/workflows/*.yml` → no matches; no husky/lint-staged config found).
- **Evidence**:
  ```ts
  // vitest.config.ts:96-103
  thresholds: { lines: 85, functions: 85, branches: 80, statements: 85 },
  skipFull: false,
  ```
  ```yaml
  # .github/workflows/frontend-typecheck.yml — the ONLY frontend CI job
  - name: TypeScript type-check (production)
    run: pnpm run type-check:prod
  ```
- **Impact**: The 214-file suite runs only when a developer remembers to. Nothing gates merges on tests passing or coverage holding. The `thresholds` block implies an enforced gate that does not exist — this is the systemic root cause that let the known ~138-spec failure baseline accumulate, and the reason every other finding in this report could land silently.
- **Related**: FE-Y5, FE-D1 (both describe missing test classes that would still not run without this).
- **Suggested Fix**: Add a CI workflow running `pnpm run test:run` (or the memory-safe variant) that fails on non-baseline failures/coverage regressions — or, if deferred intentionally, remove the `thresholds` block so the config stops implying enforcement.

---

## LOW Findings

### FE-C2: 10 components exceed the 300-line single-responsibility limit
- **Severity**: LOW · **Dimension**: Component Quality · **Status**: NEW
- **Location**: see list below
- **Description / Evidence**:
  ```
  390 components/library/Items/albums/CozyAlbumGrid.tsx
  388 components/library/TrackList.tsx                    (dead — FE-C1)
  372 components/shared/CacheHealthMonitor.tsx            (dead — FE-C1)
  356 components/shared/CacheHealthWidget.tsx             (dead — FE-C1)
  351 components/shared/SimilarTracksModal/SimilarTracksModal.tsx
  335 components/player/Player.tsx
  331 components/player/ProgressBar.tsx
  321 components/enhancement/StreamingErrorBoundary.tsx   (dead — FE-C1)
  309 components/enhancement/PlayerEnhancementPanel.tsx   (dead — FE-C1)
  308 components/library/CozyLibraryView.tsx
  ```
- **Impact**: 5 of 10 are resolved by the FE-C1 deletion. The 5 live offenders are all 308–390 lines and already delegate substantial logic to hooks — not urgent.
- **Suggested Fix**: Delete the dead 5; trim the live 5 on next touch by extracting remaining inline style/markup blocks.

### FE-R5: `queueSlice.nextTrack`/`previousTrack` are a dead, backend-unaware duplicate of the real skip flow
- **Severity**: LOW · **Dimension**: Redux State · **Status**: NEW
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:193-228`, `auralis-web/frontend/src/hooks/shared/useReduxState.ts:180-181`
- **Description**: Full repeat-mode-aware `nextTrack`/`previousTrack` reducers mutate `currentIndex` client-side with no API call and no WebSocket round-trip. The real skip flow is `usePlaybackControl.next()/previous()` (`auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:255-292`), which POSTs and waits for `track_changed`. Grepping every `useQueue()` consumer confirms neither ever calls `.next()`/`.previous()`.
- **Evidence**:
  ```ts
  // useReduxState.ts — dispatches ONLY the local reducer, no backend call
  const next = useCallback(() => dispatch(queueActions.nextTrack()), [dispatch]);
  ```
- **Impact**: None today (unreachable). If a future component wires `useQueue().next()` expecting parity with `usePlaybackControl().next()` — same name, same apparent purpose — Redux would advance without telling the backend, showing a different track than the engine is streaming, with no error surfaced.
- **Suggested Fix**: Remove the client-only reducers and their `useQueue()` wrappers, or rename/document them as local-only browsing helpers distinct from playback skip.

### FE-R6: `PlayerControls`'s preset selector writes only to Redux, bypassing the enhancement API/stream-reissue path
- **Severity**: LOW · **Dimension**: Redux State · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/shared/PlayerControls/PlayerControls.tsx:98-103`, `auralis-web/frontend/src/hooks/shared/useReduxState.ts:77-80,107`
- **Description**: `player.preset` is a legitimate **read** mirror of backend state (synced from every `player_state` snapshot, consumed by `useEnhancedPlaybackShortcuts`). But `usePlayerActions().setPreset` dispatches straight into Redux with no API call, while the real live path `useEnhancementControl().setPreset` (`auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:304-361`) POSTs to `/api/player/enhancement/preset` and re-issues the active stream.
- **Impact**: Latent, not live — `PlayerControls` has no production import site (referenced only by its own barrel and tests). If mounted, selecting a preset would flash the new value, do nothing to the audio, then silently revert on the next snapshot.
- **Suggested Fix**: Delete `PlayerControls`/`usePlayerActions().setPreset` as unused, or repoint its `PresetSelector` at `useEnhancementControl().setPreset` like every other live preset UI.

### FE-R7: `errorTrackingMiddleware`'s `errorActions` config field is defined but never read
- **Severity**: LOW · **Dimension**: Redux State · **Status**: NEW
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:54,138`
- **Description**: `ErrorTrackingConfig.errorActions` (default `['setError', 'setLastError']`) reads like a scoping allowlist, but the middleware body never references it — detection is entirely driven by the generic `payload.error` / `type.includes('Error'|'Failure'|'setError')` heuristic. Distinct from the already-fixed `enabled` flag (#4453); `errorActions` was never wired up and has no test.
- **Impact**: None today (the only call site never customizes it). A future engineer passing a custom list gets no effect and no warning.
- **Suggested Fix**: Wire it into the detection branch or delete the field and its default.

### FE-D4: Scattered raw pixel values in spacing props instead of `tokens.spacing.*`
- **Severity**: LOW · **Dimension**: Design System · **Status**: NEW
- **Location**: e.g. `auralis-web/frontend/src/components/enhancement/StreamingProgressBar.styles.ts:90,122,141-166`, `auralis-web/frontend/src/components/shared/ContextMenu/PlaylistSection.tsx:26,38,53`, `auralis-web/frontend/src/components/navigation/AuroraLogo.styles.ts:31`
- **Description**: 20 production files set `padding`/`margin`/`gap` with literal pixel strings duplicating the spacing scale — and some values are silently *off*-scale (there is no `8px` step; `sm` is 6px, `md` is 12px).
- **Impact**: Cosmetic drift only; future spacing-scale changes will miss these sites. Several cited files are inside the FE-C1 dead trees.
- **Suggested Fix**: Batch-replace with the nearest `tokens.spacing.*` step during unrelated passes; not worth a dedicated migration.

### FE-T4: Aggregate `any` usage — 69 non-test occurrences, 29 in production code across 13 files
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW
- **Description**: Repo-wide grep for `: any`, `as any`, `<any>`, `any[]`: 579 total including tests; 69 outside test dirs; of those, 40 are still test infrastructure (`test/mocks/handlers.ts` 28, `test/mocks/websocket.ts` 6, `test/setup.ts` 5, `test/mocks/api.ts` 2). The remaining **29** are production, spread 1–4 per file across `performance/lazyLoader.tsx` (8, generic dynamic-import wrapper), `performance/useRenderProfiler.ts` (4), `services/api/standardizedAPIClient.ts` (3), `utils/serviceFactory.ts` (2), `store/middleware/loggerMiddleware.ts` (2), `a11y/focusManagement.ts` (2), plus singles in `services/similarityService.ts`, `performance/withMemo.tsx`, `performance/bundleAnalyzer.ts`, `hooks/app/keyboardShortcutDefinitions.ts`, `design-system/primitives/Text.tsx`, `components/shared/DropZone/useDropZone.ts`.
- **Evidence**:
  ```ts
  // services/api/standardizedAPIClient.ts:126,133 — on the real API-response path
  export function isSuccessResponse<T>(response: any): response is SuccessResponse<T> { ... }
  export function isErrorResponse(response: any): response is ErrorResponse { ... }
  ```
- **Impact**: Mostly generic/dev-tool code. The exception worth fixing: type guards taking `any` instead of `unknown` mean a caller can pass an already-wrong-shaped value and get false-positive narrowing with no compiler pushback.
- **Suggested Fix**: Change `isSuccessResponse`/`isErrorResponse` to `unknown` (their bodies already do defensive checks); narrow the `DropZone` `(entry as any).fullPath` cast to the real `FileSystemEntry` interface. The rest are acceptable.

### FE-T5: Dead `Fingerprint`/`FingerprintResponse` types no longer match the real 25D fingerprint schema
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW
- **Location**: `auralis-web/frontend/src/types/api.ts:260-276`
- **Description**: `api.ts` still exports a flat `Fingerprint { trackId, loudness, crest, centroid, spectralFlux, mfcc, chroma, timestamp }` with zero real importers (the plausible-looking hits in `hooks/fingerprint/` are unrelated locally-declared `TrackFingerprintResponse`/`AlbumFingerprintResponse`). The canonical type used by all 14 real importers is `AudioFingerprint`, re-exported from `auralis-web/frontend/src/types/domain.ts:210` — a 25D shape bearing no resemblance to this one.
- **Impact**: None today; same landmine risk as FE-T2 — `api.ts` is the visually prominent place to grep for a "Fingerprint" type.
- **Suggested Fix**: Delete both, same #4372-style cleanup.

### FE-T6: tsconfig strictness and current tsc baseline (informational)
- **Severity**: LOW · **Dimension**: Type Safety · **Status**: NEW
- **Location**: `auralis-web/frontend/tsconfig.json:18-24`
- **Description**: `strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch` are all on. Not enabled: `noUncheckedIndexedAccess` and `noImplicitReturns`. No `@ts-ignore`/`@ts-expect-error` outside `test/setup.ts` (2, both benign), and no `eslint-disable` targeting `@typescript-eslint`/`no-explicit-any` anywhere in `src/`. Current `pnpm run type-check` error count: **208**, all in `__tests__`/`.test.` files — production source compiles with **zero** errors. This is a decrease from the historical 332 baseline, not a regression.
- **Suggested Fix**: Consider enabling `noUncheckedIndexedAccess` in a follow-up pass; not urgent given the clean production baseline.

### FE-H3: Dead-code races in unused `useFingerprintCache.ts` exports
- **Severity**: LOW · **Dimension**: Hook Correctness · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:213-282`
- **Description**: `useIsFingerprintCached`, `useCachedFingerprint`, and `useFingerprintCacheStats` each run an async IIFE inside `useEffect` and `setState` on resolution with no `isActive`/mounted guard and no request-id check against the current `trackId` prop. If `trackId` changes before resolution, the stale result wins. Verified unreachable — none are imported outside their own test files.
- **Evidence**:
  ```ts
  // useFingerprintCache.ts:216-224
  useEffect(() => {
    const checkCache = async () => {
      const cached = await getFingerprintCache().has(trackId);
      setIsCached(cached); // no isActive / trackId-still-current check
    };
    checkCache().catch(console.error);
  }, [trackId]);
  ```
- **Impact**: None currently (dead code). Would become a real stale-response bug the moment any is wired into a component with a changing `trackId`.
- **Siblings**: `useQueueFetch.ts`, `useQueueHistory.ts`, `useArtworkPalette.ts` (`isActive`), `useSimilarTracks.ts` (`currentRequestRef` + `AbortController`) all show the correct established pattern. The equivalent problem in `useRestAPI.ts`'s `useQuery` is covered by FE-A5.
- **Suggested Fix**: Delete the three unused exports, or add the same `isActive`/request-id guard before shipping them.

### FE-H4: `useFingerprintStatus`'s subscribe effect depends on the whole `wsContext` object
- **Severity**: LOW · **Dimension**: Hook Correctness · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useFingerprintStatus.ts:96-106`
- **Description**: The dep array is `[wsContext]`, but `WebSocketContext`'s memoized value (`auralis-web/frontend/src/contexts/WebSocketContext.tsx:234-257`) changes identity whenever `isConnected`/`connectionStatus` change — every connect/disconnect/reconnect/error transition. `subscribe` itself is identity-stable, so this unsubscribes and resubscribes on every status flicker rather than only on genuine reconnect.
- **Impact**: Extra dev log churn and redundant Set operations on every WS status transition. No functional bug and no listener leak (verified: cleanup always fires before the next subscribe).
- **Siblings**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts:93-100` has the identical pattern for its `seek_started` subscription.
- **Suggested Fix**: Depend on `wsContext.subscribe` directly, matching `useWebSocketMessages.ts`.

### FE-H5: `useKeyboardShortcuts`'s handler-refresh `useLayoutEffect` re-registers on every render
- **Severity**: LOW · **Dimension**: Hook Correctness · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:187-233`
- **Description**: `shortcutsToRegister` is rebuilt fresh on every render (derived via `configToServiceShortcuts(...)`, a new array each call). The effect's `shortcutsRef.current !== shortcutsToRegister` check — intended per its own comment to re-register only "when the shortcut array identity changes" — is therefore true on every render, so `keyboardShortcuts.register()` runs for every shortcut on every render of any component using the config-object form.
- **Impact**: No functional bug (registration is idempotent), just wasted work scaling with render frequency.
- **Suggested Fix**: Memoize `shortcutsToRegister` with `useMemo` keyed on the `serializedKey` already computed at lines 193-195, keeping handlers fresh via a ref.

### FE-A4: Three parallel HTTP client layers coexist
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/utils/apiRequest.ts`, `auralis-web/frontend/src/hooks/api/useRestAPI.ts`, `auralis-web/frontend/src/services/api/standardizedAPIClient.ts`
- **Description**: Three independent fetch wrappers, each reimplementing timeout, partial retry/backoff, and error normalization: `apiRequest.ts` (used by most services), `useRestAPI.ts` (a React hook with its own loading/error state), and `StandardizedAPIClient`/`CacheAwareAPIClient` (scoped narrowly to `/api/cache/stats` and `/api/cache/health` via `useStandardizedAPI.ts`). All three independently reimplement timeout-via-`AbortController`; `apiRequest.ts:14-18` explicitly acknowledges the duplication ("Matches the 30s timeout already used by the app's other two HTTP layers … so all three behave the same (#4442)").
- **Impact**: Low today given `StandardizedAPIClient`'s small blast radius, but any future fix to timeout/retry/error-shape logic (e.g. #4467) must be applied in up to three places with nothing enforcing it.
- **Suggested Fix**: Track as tech debt: converge on `apiRequest.ts` with `useRestAPI` as a thin React-state wrapper, retiring `StandardizedAPIClient` for its two remaining endpoints.

### FE-A5: `useQuery`/`useMutation` in `useRestAPI.ts` are dead code with a latent state-after-unmount bug
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:354-422`
- **Description**: Both are exported (and re-exported from `hooks/api/index.ts`) but nothing imports them — every `useQuery`/`useMutation` usage in the app resolves to `@tanstack/react-query` (confirmed: `grep -rln "from '@/hooks/api'"` returns zero matches). The custom `useQuery`'s catch block does not special-case `AbortError`/`StaleRequestError` the way the underlying `get()` does (`useRestAPI.ts:120-127` re-throws them without `setError`), and the effect has no cleanup at all.
- **Evidence**:
  ```ts
  // useRestAPI.ts:360-373
  const result = await get<T>(endpoint);
  setData(result);
  ...
  } catch (err) {
    setError(ApiErrorHandler.parse(err));   // no AbortError/StaleRequestError guard
  }
  ```
- **Impact**: None currently (unreachable). A maintenance trap: the next engineer reaching for `useQuery` from `@/hooks/api` — a very reasonable, on-brand name — inherits an internal "Stale response" string surfaced as a user-facing error plus a set-state-after-unmount warning.
- **Related**: FE-H3 (same class, different module).
- **Suggested Fix**: Delete both (all real call sites use `@tanstack/react-query`), or fix the guard and add unmount/overlap tests.

### FE-A6: Four `useAppDragDrop` fetch calls have no timeout or AbortController
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:140-231`
- **Description**: `handleAddToQueue`, `handleAddToPlaylist`, `handleReorderQueue`, `handleReorderPlaylist` each call `fetch()` directly with no `signal` and no timeout — unlike essentially every other hook-level fetch in the codebase (`useLibraryPagination`, `useLibraryStats`, `useLibraryScan`, `usePlayTrack`, `useMetadataForm`, `useAlbumDetails`, `useArtistDetailsData`, `useEnhancementParameters`, all of which wire up an `AbortController`).
- **Evidence**:
  ```ts
  // useAppDragDrop.ts:140-147
  const response = await fetch('/api/player/queue/add-track', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_id: trackId, position }),
  });
  // no signal, no timeout
  ```
- **Impact**: Low probability (requires a genuinely hung backend, not a 4xx/5xx — those are handled). When it happens the user gets a silent indefinite hang with zero feedback, since drag-and-drop has no loading indicator either.
- **Siblings**: All four handlers in the same file.
- **Suggested Fix**: Route these through `apiRequest.ts`'s `post`/`put`, which already default to a 30s timeout via `fetchWithTimeout`.

### FE-A7: Dead telemetry sink — `captureErrorToServer` posts to a nonexistent `/api/errors` endpoint
- **Severity**: LOW · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:344-361`
- **Description**: Sends tracked Redux errors to `/api/errors` via `sendBeacon`/`fetch`, but no such route exists under `auralis-web/backend/routers/` (verified repo-wide). Only invoked when `logToServer` is true, which defaults to `false` and is never enabled by the store wiring — so the path never executes today.
- **Impact**: None today. If someone flips `logToServer: true` expecting server-side aggregation it will silently 404 — or, in production, get the SPA's `index.html` back via the backend's catch-all `StaticFiles(html=True)` mount, masking the failure further since the response is never checked.
- **Suggested Fix**: Implement `POST /api/errors` or remove the dead `logToServer` path.

### FE-P2: `performance/` optimization toolkit is entirely dead code
- **Severity**: LOW · **Dimension**: Performance · **Status**: NEW
- **Location**: `auralis-web/frontend/src/performance/index.ts`, `withMemo.tsx`, `useRenderProfiler.ts`, `lazyLoader.tsx`, `bundleAnalyzer.ts`
- **Description**: The whole directory, labeled "Phase C.4b: Performance Optimization," documents itself as the app's answer to render profiling, memoization, bundle budgets, and route splitting. Nothing outside it imports it (`grep -rl "from '@/performance"` across `components/`, `hooks/`, `store/` → zero). The working versions of these concerns were built independently elsewhere: real code-splitting uses plain `React.lazy()` in `ComfortableApp.tsx`/`CozyLibraryView.tsx`, and real selector memoization uses `auralis-web/frontend/src/store/selectors/selectorPerformance.ts`.
- **Impact**: No runtime cost (tree-shaken), but misleading dead weight that duplicates the exact concern the codebase actually needs — `withMemo()` sits unused a few directories from FE-P1's missing `React.memo` calls — and implies render/bundle monitoring is active when it is not.
- **Suggested Fix**: Delete the directory (the codebase has settled on plain `React.memo`/`useMemo` + reselect), or wire `withMemo`/`useRenderProfiler` into the FE-P1 gap.

### FE-P3: Main app chunk eagerly bundles Redux, React Query, drag-and-drop, and the full Player/Queue UI
- **Severity**: LOW · **Dimension**: Performance · **Status**: NEW
- **Location**: `auralis-web/frontend/vite.config.mts:122-145`, `auralis-web/frontend/src/ComfortableApp.tsx:9-11`
- **Description**: `manualChunks` splits only `react`/`@mui`/`@emotion` into a `vendor` chunk; Redux Toolkit, react-redux, `@tanstack/react-query`, `@tanstack/react-virtual`, `@hello-pangea/dnd`, the WebSocket context, and `Player`/`QueuePanel` all ship in the single eager `App` chunk. Measured at audit time: `vendor-*.js` ~692KB raw / ~215KB gzip; `App-*.js` ~324KB raw / ~96KB gzip. Only `CozyLibraryView`, `SettingsDialog`, `EditMetadataDialog`, `KeyboardShortcutsHelp`, and `DropZone` are `React.lazy()`-split.
- **Impact**: Electron over localhost — no network latency, so this is a one-time startup disk-read + parse cost, not compounding. Still real avoidable startup work: neither `@hello-pangea/dnd` nor `@tanstack/react-query` is needed before first paint.
- **Siblings**: None — MUI icons are already 100% deep-imported (136 call sites, 0 barrel imports), so no further easy tree-shaking wins exist.
- **Suggested Fix**: Low priority; if pursued, split `@hello-pangea/dnd` into its own chunk or defer its import until the queue panel is first expanded.

### FE-Q3: Dead, drifted duplicate mock-fixture module shadows the real one
- **Severity**: LOW · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `auralis-web/frontend/src/test/mocks/api.ts:120-227`
- **Description**: Exports a full parallel fixture set (`mockTrack`, `mockAlbums`, `mockPlayerState`, `mockProcessingJob`, `mockLibraryStats`, `mockScanProgress`, plus `mockFetch`/`mockApiEndpoint`/`mockApiError`) that nothing in the 214-spec suite imports. Meanwhile `auralis-web/frontend/src/test/mocks/mockData.ts` defines same-named fixtures that ARE wired into the MSW handlers actually used by tests — and the two have already drifted.
- **Evidence**:
  ```ts
  // test/mocks/api.ts:180-190 — dead, unimported, different field names
  repeat: 'none',       // real message field is 'repeat_mode', values 'off'|'all'|'one'
  shuffle: false,
  ```
- **Impact**: Low today, but an attractive nuisance: a future test author searching `test/mocks/` for `mockPlayerState` has a 50/50 chance of asserting against field names that match no real contract.
- **Suggested Fix**: Delete `test/mocks/api.ts` (folding any useful helper into `handlers.ts`/`server.ts`) so there is a single fixture source.

### FE-Y6: `IconButton`'s `tooltip` prop does not grant an accessible name
- **Severity**: LOW · **Dimension**: Accessibility · **Status**: NEW
- **Location**: `auralis-web/frontend/src/design-system/primitives/IconButton.tsx:189-196`, `auralis-web/frontend/src/components/settings/FoldersList.tsx:63-69`
- **Description**: The `tooltip` prop only wraps the button in an MUI `<Tooltip>` (which adds `aria-describedby` — a *description*, not a *name*) and only when `tooltip && !disabled`; it never sets `aria-label`. The component's own docstring implies `tooltip` alone is sufficient. A sweep of all 22 `<IconButton>` usages found all but one pass an explicit `aria-label`; `FoldersList.tsx:63` (the remove-scan-folder button) relies on `tooltip` alone, leaving `<DeleteIcon />` with no accessible name.
- **Evidence**:
  ```tsx
  // IconButton.tsx
  if (tooltip && !disabled) { return <Tooltip title={tooltip} arrow>{button}</Tooltip>; }
  ```
- **Impact**: Screen-reader users hear an unnamed "button" in Settings → Folders. Also, since the wrapper is skipped entirely when `disabled`, any future disabled `IconButton` relying on `tooltip` loses its description while still being announced as a control.
- **Suggested Fix**: Add `aria-label="Remove this folder"` at the call site; consider having `IconButton` fall back to `tooltip` as `aria-label` when none is supplied, so the documented pattern is accessible by default.

### FE-Y7: Card play-button overlay is invisible when reached by keyboard focus
- **Severity**: LOW · **Dimension**: Accessibility · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/shared/MediaCard/MediaCardOverlay.tsx:35-89`, `auralis-web/frontend/src/components/shared/MediaCard/MediaCard.tsx:96-121`
- **Description**: `showOverlay = isHovered || isPlaying` is driven only by mouse hover (`onMouseEnter`/`onMouseLeave`) and the `isPlaying` prop — never by keyboard focus. The overlay `IconButton` (`opacity: showOverlay ? 1 : 0`) stays in the DOM and in tab order at all times, so a keyboard user can land focus on a fully transparent Play button with no visual indication.
- **Impact**: A sighted keyboard-only user tabbing a card grid can silently focus an invisible Play button (distinct from the outer card, which does have a visible `:focus-visible` outline) — pressing Enter plays a track with no prior visual cue. WCAG 2.4.7 gap on this nested control.
- **Siblings**: `MediaCardOverlay` is shared by `AlbumCard` and `TrackCard` via `MediaCard`, so this affects the play overlay across the whole unified card system.
- **Suggested Fix**: Add `isFocused` state via `onFocus`/`onBlur` on the `IconButton`, or drive `showOverlay` off a CSS `:focus-within` on the card.

---

## Confirmed Existing (not counted as new)

| ID | Issue | Severity | Verification |
|----|-------|----------|--------------|
| FE-C3 | **#4428** — QueuePanel list key mixes array index into a memoized row's identity | MEDIUM | Still present at `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:245`, where the row key still interpolates the volatile virtual-row index alongside `track.id`. Independently rediscovered by two dimensions. Compounds with FE-P1: `QueuePanel` already re-renders more than necessary, and this additionally defeats `QueueTrackItem`'s `#4177` memo on every reorder, unmounting/remounting shifted rows and resetting their hover/focus state. |
| FE-R4 | **#4430** — errorTrackingMiddleware mislabels any slice's network-flavored error as a connection error | MEDIUM | Still present at `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:69-122,286-296`, unchanged. |

Also verified still-open and deliberately not re-reported: #4426, #4459, #4463, #4464, #4466, #4467, #4471, #4472, #4485, #4486, #4488, #4489, #4490, #4491, #4492, #4493, #3256, #3654, #3894, #3895, #4399.

---

## Relationships

**Cluster A — the theme unification stopped at the chrome boundary.**
`FE-D3` (three competing color APIs) is the enabling condition: with no single canonical way to get a color, `FE-D1` (149 files on raw dark-only primitives) and `FE-D2` (a component that migrated only half its states) were the natural outcome. `FE-Y4` is the same problem on a different axis — a token used outside its documented calibration — and `FE-D1`'s missing light-mode contrast test is the same structural blind spot `FE-Y5` describes generally. Fixing `FE-D3` first makes the rest mechanical; fixing `FE-D1` without it leaves the next author the same three choices.

**Cluster B — un-migrated duplicate components.**
`FE-C1` (dead enhancement/library subtrees), `FE-Y2` (the artist page's own `AlbumCard` instead of the unified one), `FE-A2` (two track transformers), `FE-R5`/`FE-R6` (a second, backend-unaware skip and preset path), and `FE-A4` (three HTTP layers) are all the same failure: a migration landed for the primary path and the secondary path was left behind rather than deleted. `FE-Y2` is HIGH precisely because the un-migrated duplicate is still *reachable* — everything else in this cluster is dead, which is why it is MEDIUM/LOW.

**Cluster C — dead code with false coverage.**
`FE-C1`, `FE-P2`, `FE-T2`, `FE-T5`, `FE-H3`, `FE-A5`, `FE-A7`, `FE-R5`, `FE-R7`, `FE-Q3`. Several carry passing tests (`TrackList.test.tsx`, `enhancement/__tests__/*`), which is worse than no tests: it inflates apparent coverage for paths that never execute. Deleting this cluster resolves 5 of FE-C2's 10 oversized components and 2 of FE-Y4's 8 contrast sites for free.

**Cluster D — the unvalidated backend boundary.**
`FE-T3` (no runtime validation at `apiRequest`) is the root; `FE-A1` (tracks bypasses the transformer), `FE-A2` (two transformers to forget), `FE-T1` (a backend broadcast with no frontend type), and `FE-T2` (types drifted from routers) are all instances that this boundary structurally cannot catch. Each was previously discovered only after visible breakage (#3593, #3976, #4440, #4418) — the same detection latency will apply to the next one.

**Cluster E — the missing gate.**
`FE-Q2` (no CI runs tests) sits under everything else. `FE-Q1` (untested WS→Redux sync), `FE-Y5` (no a11y testing), and `FE-D1`'s dark-only contrast test all describe missing coverage that would still not run even if written. Fix `FE-Q2` first or every other test-related fix in this report is unenforced.

**Render-path chain.** `FE-H1` (unstable `playEnhanced` identity) → `FE-P1` (unmemoized `Player` children) → `#4428` (index-in-key defeats `QueueTrackItem`'s memo). These must be fixed in that order: memoizing `QueuePanel` (FE-P1) accomplishes little while `handleNext`/`handlePlayPause` change identity every render (FE-H1), and the row-level memo stays defeated until the key is stable (#4428).

---

## Prioritized Fix Order

1. **FE-D1 + FE-D2** — light mode currently renders invisible text on the library grid, artist list, and every media card. This is user-visible breakage of a feature that shipped three days ago; fix before anyone toggles the theme. Pair with the parametrized light/dark contrast test so it stays fixed.
2. **FE-Y1 + FE-Y2** — two core flows (queue reorder, artist → album) are unusable without a mouse. FE-Y2 is a component swap (an afternoon); FE-Y1 needs a small keyboard handler on an existing hook.
3. **FE-Q2** — add a CI job that runs the suite. Without it, every fix below is unenforced and the failure baseline keeps growing. Cheapest high-leverage item in the report.
4. **FE-D3** — retire the legacy `themeConfig` color API and the dead CSS aliases. One live call site remains; doing this before the bulk FE-D1 migration removes the ambiguity that caused it.
5. **FE-A1** — a one-line fix (`case 'tracks': return transformTracks(...)`) closing a silent `undefined` leak that will bite the next feature built on `useTracksQuery`. Add the missing mapping test alongside.
6. **FE-C1 + Cluster C** — delete the dead code in one pass. Resolves half of FE-C2, two of FE-Y4's sites, and removes the false-coverage suites. Large diff, near-zero risk, and it shrinks the surface every subsequent audit must read.
7. **FE-H1 → FE-P1 → #4428** — in that order (see the render-path chain above). Continuous 10Hz CPU churn during all playback on a machine also running the DSP engine.
8. **FE-R2 + FE-R1 + FE-R3** — the Redux/WebSocket consistency set. FE-R2 (staleness guard on discrete events) is the one with a real wrong-state outcome; FE-R1 and FE-R3 are visible-inconsistency fixes.
9. **FE-Y4 + FE-Y3 + FE-Y5** — remaining a11y. FE-Y5 (`vitest-axe`) is worth doing before the others so the fixes are verified rather than asserted.
10. **FE-T1, FE-T2, FE-T3, FE-A2, FE-A3, FE-H2** — contract and correctness hardening. FE-T3 should be scoped to guards on the highest-traffic endpoints only; a full runtime-schema rewrite is disproportionate for a localhost-only single-consumer app.
11. **Remaining LOW** — opportunistically, ideally batched into whatever file each touches.

---

## Coverage Notes — Investigated and Found Correct

Recorded so future audits do not re-litigate these:

- **WebSocket layer**: `contexts/WebSocketContext.tsx` routes messages to typed per-type `Set<MessageHandler>` maps with a context value memoized over only `isConnected`/`connectionStatus` — a dispatch does not change context identity and does not re-render unrelated subscribers. StrictMode remount handling (#4436), binary-frame/Blob pairing (#4331), ping/pong keepalive (#4406), and stream resume tracking (#3185/#3345/#3759/#3763) all verified correct on re-read. The audit's headline performance hypothesis was **disproven**; `position_changed` is also 1Hz server-side (`auralis-web/backend/core/state_manager.py:238`), not 10Hz.
- **Hook cleanup**: every `setInterval`/`setTimeout`/`addEventListener`/`requestAnimationFrame` site across all 114 hook files has matching cleanup. Every `eslint-disable react-hooks/exhaustive-deps` in the player domain has a justifying comment that checks out. `useArtworkPalette`, `useSimilarTracks`, `useLibraryPagination`, `useLibraryScan`, `useLibraryStats`, `useQueueFetch`, `useQueueHistory`, `usePlayTrack` all correctly guard async setState.
- **Redux**: all derived selectors are `createSelector`-backed; every `useSelector` call site (16 total) uses a module-level selector or a direct property accessor — no inline `.map()`/`.filter()`/object-literal selectors. All slice state is plain JSON-shaped (the `CacheStats.tracks` Map is stripped before entering the store per #3623/#3967). `playerSlice.preset` is **not** dead state — it is an active read-mirror of backend `current_preset`.
- **Performance**: track list, queue panel, artist list, and both album-grid sort modes are all virtualized via `@tanstack/react-virtual`. All artwork images have `loading="lazy"`. No production `createObjectURL` call sites exist, so there is no object-URL leak surface. `useArtworkRevision` uses per-album `useSyncExternalStore` to avoid the 500-albums × 1-broadcast trap (#3575). Scan progress is emitted per-batch server-side, bounded regardless of library size. MUI icons are 100% deep-imported.
- **Components**: error-boundary coverage is solid (Library and Player subtrees independently wrapped in `ComfortableApp.tsx`, plus a root boundary in `index.tsx`). List keys outside `QueuePanel` correctly use stable data ids. All async components checked guard setState after unmount. `ProgressBar.tsx` ref/drag handling is correct.
- **Accessibility**: `ProgressBar`, `PlaybackControls`, `TrackDisplay`, `TrackRow`, `ClearQueueDialog`, the unified `MediaCard`/`AlbumCard`, artwork `alt` text, and all MUI-based dialogs (focus trap / escape / `aria-modal` inherited from MUI) already implement correct ARIA and keyboard patterns.
- **Types**: production source compiles with zero tsc errors. No `@ts-ignore` outside two benign uses in `test/setup.ts`. No `eslint-disable` targeting type rules anywhere in `src/`.
- **Tests**: every "no `vi.unmock`" hit for WebSocketContext-adjacent specs was individually checked — all use legitimate local `vi.mock`/`vi.spyOn` overrides, none silently assert against the global auto-mock. `useWebSocketConnection`/`websocketConnectionCore` are thoroughly exercised via four `WebSocketContext.*.test.tsx` files that correctly `vi.unmock()`. `usePlayEnhanced`'s four sub-hooks are genuinely exercised (not mocked away) in its 900-line integration suite. No orphaned specs for deleted components; no snapshot tests exist.
- **Base URLs**: relative `fetch('/api/...')` calls are correct in both environments — `vite.config.mts` proxies `/api` and `/ws` to `:8765` in dev, and the packaged Electron app loads `http://localhost:8765` where the backend serves the built frontend via `StaticFiles`. Not a bug.
- **Import hygiene**: zero relative `../../` imports in production `src/components`/`src/pages` (the 15 known cases are all test files, tracked by #4466).

---

*Generated by `/audit-frontend` (9 dimensions, deep). Next step:*

```
/audit-publish docs/audits/AUDIT_FRONTEND_2026-07-25.md
```
