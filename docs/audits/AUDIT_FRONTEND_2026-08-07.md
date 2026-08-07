# Frontend Audit — 2026-08-07

**Scope**: `auralis-web/frontend/` — components, Redux store, hooks, TypeScript types, design system, API clients, performance, accessibility, test coverage.
**Method**: 9 dimension agents, fresh read of current source. Deduplicated against 200 open GitHub issues and the prior reports of 2026-07-12 / 2026-07-25 / 2026-07-29.
**Depth**: deep. **Limit**: none.

**Context**: The 2026-07-29 audit is only 9 days old, but 32 frontend commits have landed since — many of them explicit fixes for that report's own findings (queue-endpoint contracts, GainNode leak, theme migration, dead-tree deletion, accessibility gaps, ErrorBoundary wrapping). Every dimension agent was instructed to re-verify the prior report's claims against current source rather than assume they still held. Most did; several were fixed cleanly; two fixes were structurally correct but incomplete (Y8-01/Y8-02); and the single largest new feature landed in that window — `PlaybackSessionContext` (#4541, `591d374f`, 2026-07-30) — introduced three distinct new defects that no prior audit could have seen.

---

## Executive Summary

**16 findings — 0 CRITICAL, 2 HIGH, 6 MEDIUM, 8 LOW.**

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 2 | TC9-02, P7-01 |
| MEDIUM | 6 | C1-01, H3-01, T4-05, A6-03, Y8-02, TC9-03 |
| LOW | 8 | C1-02, R2-01, R2-02, R2-03, T4-06, A6-04, P7-02, Y8-01 |

### Verified baselines (not findings)

Measured during this audit; healthy or accurately tracked. Do not file issues against these.

| Gate | Result |
|------|--------|
| `pnpm run type-check:prod` (CI-enforced) | **0 production errors** — no regression |
| `pnpm run type-check` (full, incl. tests) | 101 errors, all in test files (was 100 on 2026-07-29) — deliberately excluded from the CI gate (#4665) |
| `pnpm run test:ci` + `pnpm run test:baseline` | **3066 passed, 251 failed, baseline cap 142/143 → 112 new failures not in baseline.** This is **TC9-02** below, not a healthy baseline — listed here only to anchor the raw numbers against the prior report's "3261 passed, 165 failed, cap 166." |
| Design-system dark-only-token migration (#4877) | Real progress: 324 refs / 103 files → 247 refs / 83 files (338/88 combined with `bg.*`). Still open; see D5 notes below. |

### Dimension coverage

All 9 dimensions declared in `.claude/commands/audit-frontend.md` were launched, completed, and persisted their output.

| # | Dimension | Status | Raw findings | Kept (NEW) |
|---|-----------|--------|--------------|------|
| 1 | Component Quality | complete | 2 | 2 |
| 2 | Redux State | complete | 3 | 3 |
| 3 | Hook Correctness | complete | 1 | 1 |
| 4 | Type Safety | complete | 2 | 2 |
| 5 | Design System | complete | 0 (5 existing updated) | 0 |
| 6 | API Client | complete | 2 | 2 |
| 7 | Performance | complete | 2 | 2 |
| 8 | Accessibility | complete | 2 | 2 |
| 9 | Test Coverage | complete | 2 | 2 |
| | **Total** | | **16** | **16** |

No cross-dimension duplicates at the same file:line were found. Two clusters of *related-but-distinct* findings exist in the same file (`PlaybackSessionContext.tsx`: H3-01/P7-01/TC9-02) and are called out under Relationships rather than merged, since each is independently reproducible and independently fixable.

### Key themes

1. **`PlaybackSessionContext` (#4541, landed one day after the last audit) introduced three separate defects across three dimensions** — a silently-dropped-command race (H3-01), a whole-app-shell 10Hz re-render cascade (P7-01, HIGH), and a missing test-provider wrap that currently breaks 111 specs and makes CI red for unrelated PRs (TC9-02, HIGH). No single prior audit could have caught this; it is new code, correctly attributed to its introducing commit by every agent that touched it.
2. **Two 2026-07-29 accessibility fixes were structurally correct but incomplete** — the "no `<h1>`" fix added a second, permanently-mounted heading instead of noticing one already existed (Y8-01), and the "orphaned `role=option`" fix added `role="listbox"` without wiring the ARIA state (`aria-selected`, roving tabindex) the multi-select feature underneath it actually needs (Y8-02). Same shape as the prior report's own Cluster 2 ("fixing at the call site rather than the choke point").
3. **Dead-code-as-recurring-shape continues** — five more "declared, exported, documented, never used" instances (R2-01, R2-02, R2-03, T4-06, plus A6-03's more dangerous variant below) join the four the prior report already tracked in this exact category. No CI gate (`knip`/`ts-prune`) exists to stop this from regrowing, as the prior report also noted.
4. **A dead type that reintroduces a bug just fixed** (A6-03) — the clearest "landmine" finding this pass: `PlayerQueueReorderRequest`'s shape is exactly the pre-A6-01 broken payload, sitting unused in the same file every service imports from.
5. **The store layer (`src/store/`) had zero commits since 2026-07-29 and zero new findings** — confirms the prior assessment that this layer is comparatively well-hardened; all three prior Redux findings (#4921, #4927, #4933) are unchanged, unregressed, and not re-reported.

### Most impactful issues

- **TC9-02** — CI is currently red for reasons unrelated to any given PR's own changes, and the very feature (#4541's global keyboard shortcuts) that introduced the gap now ships with zero passing regression coverage. Fix is a one-line addition to a test helper.
- **P7-01** — the entire app shell (sidebar, top bar, active library view) re-renders 10×/second for the full duration of every playback session — the single most common simultaneous-use pattern in a music player (browsing while listening).
- **A6-03** — a dead type shaped exactly like the bug A6-01 just fixed, sitting in the file every service imports from.

---

## Findings

### HIGH

### TC9-02: `AllProviders` test helper doesn't wrap `PlaybackSessionProvider`, breaking 111 specs and making the CI gate fail for unrelated changes
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/test/test-utils.tsx:126-138` (`AllProviders`); root cause `auralis-web/frontend/src/App.tsx:52` (#4541, `591d374f`); throw site `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:293`
- **Status**: NEW
- **Description**: `#4541` wrapped the real app tree in `<PlaybackSessionProvider>` so `Player.tsx` and `ComfortableApp`'s global keyboard shortcuts share one session. Several hooks reach it via `usePlaybackSession()`: `usePlayTrack.ts` (used across library/album/playlist views via `usePlaybackState.ts`) and `usePlaylistContextActions.ts` (used by `PlaylistList.tsx`). The shared test helper `AllProviders` renders `ReduxProvider → QueryClientProvider → BrowserRouter → ThemeProvider → ToastProvider → children` — no `PlaybackSessionProvider` anywhere in the chain. `591d374f` landed 2026-07-30, one day after `test-baseline.json` was last regenerated, so nothing caught it.
- **Evidence**:
  ```
  Error: usePlaybackSession must be used within a PlaybackSessionProvider
   ❯ usePlaybackSession src/contexts/PlaybackSessionContext.tsx:293:11
   ❯ usePlaylistContextActions src/components/playlist/usePlaylistContextActions.ts:29:26
   ❯ PlaylistList src/components/playlist/PlaylistList.tsx:158:26
   ❯ AllProviders src/test/test-utils.tsx:132:14
  ```
  `pnpm run test:baseline`: **3066 passed, 251 failed, baseline allows 143 → 112 new failures.** 111 traced individually to this root cause:

  | File | New failures |
  |---|---|
  | `AlbumDetailView.test.tsx` | 41 |
  | `PlaylistList.test.tsx` | 19 |
  | `tests/integration/library-management/library-management.test.tsx` | 20 |
  | `tests/integration/library-management/playlist-management.test.tsx` | 13 |
  | `CozyLibraryView.test.tsx` | 9 |
  | `Sidebar.test.tsx` | 6 |
  | `ComfortableApp.test.tsx` | 3 |
  | `tests/integration/websocket-realtime/websocket-realtime.test.tsx` | 1 — unrelated flake, see Suggested Fix |
- **Impact**: `frontend-test.yml`'s CI gate fails on `master` right now for reasons unrelated to whatever a given PR changes. It also deletes real coverage: the affected specs fail at the render step before any assertion runs, so `AlbumDetailView`, `PlaylistList`, both library-management integration suites, `CozyLibraryView`, `Sidebar`, and — most notably — `ComfortableApp`'s own global-shortcut tests (the tests #4541 itself added) currently provide **zero passing regression coverage** for the feature they exist to protect.
- **Suggested Fix**: Add `<PlaybackSessionProvider>` to `AllProviders`'s chain in `test-utils.tsx`, nested inside `ReduxProvider` to match `App.tsx`'s real order. Since `usePlayEnhanced()` only touches the already-globally-mocked `WebSocketContext` and existing MSW REST handlers, this should be low-risk, but re-run the full suite afterward — some specs may need a lightweight WS-context override. The 112th failure (`websocket-realtime.test.tsx`, a flaky `isConnected` timing assertion) is unrelated — worth a look, not blocking. Regenerate the baseline (`pnpm run test:baseline:update`) only *after* this fix lands, so the 111 new failures don't get silently baked into the ratchet; at that point it will also pick up 4 pre-existing failures that no longer reproduce (`SimilarityVisualization.test.tsx`, the deleted `discovery/` suite, `TrackCard.test.tsx`, `usePlayEnhanced.test.ts`).

---

### P7-01: `PlaybackSessionContext`'s single memoized value bundles a 10Hz `currentTime` field with low-frequency data, so the entire app shell re-renders 10×/second during playback
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:251-269` (the `value` `useMemo`); consumed by `ComfortableApp.tsx:66-71`, `Player.tsx`, `usePlayTrack.ts`, `usePlaylistContextActions.ts`; fed by the 10Hz tick in `hooks/enhancement/useAudioStreamingCore.ts:484-493`
- **Status**: NEW (broader root cause than, and related to, Existing: #4632)
- **Description**: `useAudioStreamingCore`'s `setInterval(..., 100)` calls `setCurrentTime` 10×/second while playing. That flows into `PlaybackSessionProvider`'s single `useMemo`'d `value`, which includes `currentTime` alongside `handlePlayPause`/`handleNext`/etc. React context has no partial subscription — every consumer re-renders on **any** field change. `PlaybackSessionProvider` wraps `<ComfortableApp />` at the app root (`App.tsx:52-54`); `ComfortableApp` consumes the context only for booleans/handlers (never `currentTime`) to wire keyboard shortcuts, but its function body still re-executes 10×/second, cascading into the unmemoized sidebar, top bar, and active (potentially virtualized, hundreds-of-rows) library view.
- **Evidence**:
  ```ts
  // useAudioStreamingCore.ts:484-493 — the 10Hz source
  const interval = setInterval(() => {
    const time = playbackEngineRef.current?.getCurrentPlaybackTime() || 0;
    setCurrentTime((prev) => (time === prev ? prev : time));
  }, 100);
  ```
  ```ts
  // PlaybackSessionContext.tsx:251-269 — currentTime bundled with handlers in one memo
  const value = useMemo<PlaybackSessionContextValue>(() => ({
    isStreaming, streamingState, processedChunks, totalChunks,
    currentTime, isPaused, isSeeking, isCommandPending, error,
    startTrack, handleSeek, handlePlayPause, handleNext, handlePrevious,
    handleVolumeChange, handleMuteToggle,
  }), [/* ...all of the above... */]);
  ```
  `grep -n "memo(" AppSidebar.tsx AppTopBar.tsx AppMainContent.tsx AppContainer.tsx CozyLibraryView.tsx` → no matches.
- **Impact**: For the full duration of every playback session, the sidebar, top bar, and active library view re-render 10×/second — none of which depend on playback position. Strictly broader than the already-tracked #4632 (which only covers `Player`'s six direct children via prop drilling): this finding's root cause is the context's value shape, and the blast radius extends to the whole app shell. Visible as scroll stutter while browsing during playback on modest hardware.
- **Related**: Existing #4632 (narrower instance of the same design; fixing this finding first isolates #4632's remaining scope to `Player`'s own local-state re-renders).
- **Suggested Fix**: Split into two contexts — low-frequency `PlaybackControlsContext` (handlers, `isStreaming`, `isPaused`, `error`) and high-frequency `PlaybackProgressContext` (`currentTime`, `processedChunks`, `totalChunks`). Only `Player`/`ProgressBar` should subscribe to the latter.

---

### MEDIUM

### C1-01: `QueuePanel` calls 9 hooks after a conditional early return — the same Rules-of-Hooks defect fixed elsewhere as CRITICAL (#3924), dormant only because the sole caller hardcodes the triggering prop
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:92-168`; triggering call site `Player.tsx:163-166`
- **Status**: NEW
- **Description**: `QueuePanel` calls 11 hooks unconditionally, then at line 92 branches `if (collapsed) { return (...) }`. Nine more `useCallback`s follow that return. When `collapsed` is `true`, the component returns before calling them; when it later renders with `collapsed=false`, it calls all 20 — a mid-lifetime change in hook call order/count, the exact defect class `#3924` (CLOSED, CRITICAL) fixed in `LibraryViewRouter.tsx`, whose own comment now warns against this pattern. The project has no ESLint configured at all (no `lint` script, no `eslint*` devDependency), so `react-hooks/rules-of-hooks` never runs anywhere.
- **Evidence**:
  ```tsx
  // QueuePanel.tsx:92-104
  if (collapsed) { return (<div>...</div>); }
  // QueuePanel.tsx:107 — first of 9 hooks called ONLY when collapsed is false
  const handleRemoveTrack = useCallback(async (index: number) => {...}, [removeTrack]);
  // ...8 more through line 168
  ```
  ```tsx
  // Player.tsx:163-166 — the only render site; collapsed is a literal
  <QueuePanel collapsed={false} onToggleCollapse={() => setQueuePanelOpen(false)} />
  ```
  Confirmed via `git show c4f8f696~1` this predates the recent QueuePanel/SimilarTracksModal line-count split (#4916) — missed by it, not introduced by it.
- **Impact**: Zero runtime impact today — the only call site hardcodes `collapsed={false}`. Latent landmine: sibling `QueueRecommendationsPanel` already supports a live collapse toggle via state, so the natural next change to `QueuePanel` throws a React invariant violation on the first collapsed↔expanded transition. Contained by `Player`'s `ErrorBoundary`, but breaks active playback/queue UI with a "Player encountered an error" fallback.
- **Siblings**: Swept every `.tsx` under `components/` for the same shape; `LibraryViewRouter.tsx` is the already-fixed case (its branch returns a dedicated sub-component owning its own hooks). All other candidates (`DropZone.tsx`, `ContextMenu.tsx`, `StarfieldBackground.tsx`, `ProgressBar.tsx`, `ClearQueueDialog.tsx`, `CozyAlbumGrid.tsx`, `PlaylistList.tsx`) are false positives. `QueuePanel.tsx` is the sole live instance.
- **Suggested Fix**: Follow #3924's established pattern — extract the `!collapsed` body into a dedicated sub-component owning all nine trailing hooks, and have `QueuePanel` become a pure `collapsed ? <Collapsed/> : <Expanded/>` switch.

---

### H3-01: One shared "command pending" mutex silently drops different transport commands, and the UI falsely confirms the dropped one anyway
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:118-213` (`runTransportCommand`, `startTrack`, `handleNext`, `handlePrevious`, `handlePlayPause`); consumed with no pending check at `ComfortableApp.tsx:84-113` (keyboard shortcuts)
- **Status**: NEW (introduced by `0c4fef28`, "harden playback command lifecycle", 2026-08-03, fixing #4835)
- **Description**: `runTransportCommand` gates four distinct intents (`startTrack`, `handleNext`, `handlePrevious`, `handlePlayPause`) behind one shared `commandPendingRef` boolean — a silent, unconditional `return` with no queue, log, or error when already held. #4835's fix and its regression test were scoped to coalescing *repeated* clicks of the *same* button; the mutex has no notion of *which* command is pending, so any *different* command hitting the guard mid-flight is dropped identically. The mouse path is partially protected (`Player.tsx:124` disables transport buttons via `isCommandPending`); **global keyboard shortcuts are not** — `ComfortableApp.tsx` wires Arrow/Space directly to the session handlers with no pending check, and fires a confirmation toast ("Next track", "Paused"/"Playing") unconditionally regardless of whether the command actually ran.
- **Evidence**:
  ```ts
  const runTransportCommand = useCallback(async (command) => {
    if (commandPendingRef.current) return;   // silent, unconditional drop
    commandPendingRef.current = true;
    try { await command(); } finally { commandPendingRef.current = false; }
  }, []);
  ```
  ```tsx
  // ComfortableApp.tsx:94-101 — 'ArrowRight'
  handler: () => { nextTrack(); info('Next track'); }  // toast fires either way
  ```
- **Impact**: Pressing two different transport keys in quick succession (`→` then `Space`, or alternating `→`/`←`) has a real chance of the second command being silently discarded while the toast tells the user it happened — confusing in the highest-frequency interaction pattern for a music player.
- **Siblings**: `startTrack` (library-track clicks via `usePlayTrack.ts`) shares the same ref — clicking a track while a keyboard-issued skip is resolving drops silently the same way.
- **Related**: Regression risk against #4835 itself, whose fix correctly solved same-command coalescing but widened the guard to cross-command exclusion as an untested side effect.
- **Suggested Fix**: Either key the pending flag per logical command class (or adopt a last-issued-wins pattern via the `requestId`/`isStale()` idiom already used in `useLibraryQuery.ts`), or at minimum gate `ComfortableApp.tsx`'s keyboard handlers on `session.isCommandPending` before calling the handler or firing the toast. Add a regression test exercising *two different* rapid commands — the existing suite only covers same-command repeats.

---

### T4-05: `useQueueFetch`'s unsafe cast injects snake_case backend fields into a camelCase-typed Redux slice, corrupting `currentTrack.artworkUrl` on a live path
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueFetch.ts:43-49`; sibling correct implementation `usePlayerStateSync.ts:160-172`; live consumer `usePlayerStateSync.ts:262-266` (`track_changed` handler) and `components/player/TrackInfo.tsx:37-39`
- **Status**: NEW (flagged as an out-of-scope "sibling risk" in the now-CLOSED #4787, never itself filed or fixed)
- **Description**: `GET /api/player/queue` returns snake_case `TrackInfo` (`artwork_url`, no `filepath`). `useQueueFetch` does `response.tracks as (Track | QueueTrack)[]` — a bare assertion, not a transform — and dispatches straight into the camelCase-typed `queue` slice. The sibling WS path (`usePlayerStateSync.ts:160-172`) does this correctly with an explicit field-by-field map. `isQueueResponseShape` only checks for a numeric `id`; it cannot catch a casing mismatch.
- **Evidence**:
  ```ts
  // useQueueFetch.ts:43-49
  const response = await get<Record<string, unknown>>('/api/player/queue', { validate: isQueueResponseShape });
  dispatch(reduxSetQueue((response.tracks as (Track | QueueTrack)[]) || []));
  ```
  ```ts
  // usePlayerStateSync.ts:160-172 — the correct sibling
  const tracks = state.queue.map((t: TrackInfo) => ({ ..., artworkUrl: t.artwork_url }));
  dispatch(setQueue(tracks));
  ```
- **Impact**: Live, not merely latent. `usePlayerStateSync.ts:262-266` handles `track_changed` (sent on every skip/auto-advance) by reading `store.getState().queue.tracks` directly and dispatching `setCurrentTrack(tracks[index])` with **no transform**. If `track_changed` arrives before the first full `player_state` WS snapshot overwrites the REST-seeded queue (a real race on cold start, `--dev` reload, or WS reconnect racing a REST refetch), `currentTrack` ends up typed `artworkUrl` but actually holding `artwork_url`. `TrackInfo.tsx:37-39` (the Now Playing bar) reads `track.artworkUrl` directly — producing blank album art with no compiler or runtime error. #4787's own fix commit assessed this path as "latent since no renderer reads artwork from here," which didn't account for the `track_changed` reuse of the raw array.
- **Suggested Fix**: Extract `usePlayerStateSync.ts:160-166`'s mapping into a shared `mapTrackInfoToTrack()` helper and use it in both places instead of the raw cast.

---

### A6-03: `PlayerQueueReorderRequest` is dead code whose shape reflects the exact pre-A6-01 broken contract — reaching for it reintroduces the bug A6-01 just fixed
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/types/api.ts:86-89`
- **Status**: NEW
- **Description**: `PlayerQueueReorderRequest { from_index: number; to_index: number }` has zero import sites anywhere. Its name and shape describe exactly the payload `useQueueMutations.reorderTrack` used to send to `PUT /api/player/queue/reorder` before A6-01 was fixed (#4854) — that route actually requires `{new_order: number[]}`; this shape only fits the *different* endpoint `/queue/move`. The current, correct call site builds the object as an inline literal rather than importing the type, so it sat unused and unnoticed through the fix.
- **Evidence**:
  ```ts
  // types/api.ts:86-89 — zero importers anywhere in src/
  export interface PlayerQueueReorderRequest { from_index: number; to_index: number; }
  ```
- **Impact**: No live path affected today, but it's exported from `types/api.ts` — a file every service imports from — with the single most misleading possible name for its shape. A future contributor fixing a `/queue/reorder` bug who greps for a reorder-request type will find this one; using it against `/queue/reorder` reproduces A6-01 (a 422 on every reorder) verbatim. Same failure mode as T4-02 (already fixed).
- **Siblings**: `types/api.ts` has a broader dead-type cluster (`PlayerPlayRequest`, `PlayerSeekRequest`, `PlayerVolumeRequest`, `PlayerQueueAddRequest`, `PlayerQueueRemoveRequest`, `MasteringRecommendationResponse`) — lower severity since their shapes are merely inert, not actively misleading.
- **Suggested Fix**: Delete `PlayerQueueReorderRequest` (or repurpose as `MoveQueueTrackRequest`'s frontend type and have `reorderTrack`'s literal import it). Sweep the sibling dead types in the same pass — pure deletions, no call-site changes needed.

---

### Y8-02: Track listbox declares `aria-multiselectable="true"` but options never expose `aria-selected`, and there is no arrow-key roving navigation
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:94-99`; `components/library/Items/tracks/SelectableTrackRow.tsx:76-108`; `components/library/Items/tracks/TrackRow.tsx:105-123`
- **Status**: NEW
- **Description**: `014da248` fixed 2026-07-29's Y8-01 (orphaned `role="option"`, no `listbox` ancestor) by adding `role="listbox"`/`aria-multiselectable="true"`. That closes the structural ARIA violation, but the app's real multi-select feature (`SelectableTrackRow`, driven by `BatchActionsToolbar`) isn't actually wired to the pattern this now declares: (1) `isSelected` is used only for CSS/checkbox state in `SelectableTrackRow` and never forwarded to `TrackRow`'s `role="option"` element — `aria-selected` never appears anywhere in `src/components/library`; (2) every row gets `tabIndex={0}` unconditionally instead of roving tabindex, and there is no `ArrowUp`/`ArrowDown`/`Home`/`End` handling anywhere in the three files — only `Enter`/`Space` to play.
- **Evidence**:
  ```tsx
  // TrackListViewContent.tsx:94-99
  <div role="listbox" aria-label="Track list" aria-multiselectable="true">
  ```
  ```tsx
  // SelectableTrackRow.tsx — isSelected drives CSS/checkbox only, never reaches TrackRow
  <TrackRow track={track} index={index} isPlaying={isPlaying} isCurrent={isCurrent} ... />
  {/* no isSelected prop passed */}
  ```
  `grep -rn "aria-selected" src/components/library` → zero matches.
- **Impact**: Screen-reader/keyboard-only users cannot perceive which tracks are selected for batch actions short of separately focusing each row's checkbox, and cannot use the arrow-key navigation model `role="listbox"` advertises. A partially-implemented ARIA pattern — better than the pre-fix orphaned role, but missing the two properties (`aria-selected`, roving focus) `aria-multiselectable` exists for.
- **Related**: Existing #4637 (no automated a11y testing — an `axe-core` pass would catch the missing `aria-selected` directly).
- **Suggested Fix**: Thread `isSelected` into `TrackRow`, set `aria-selected={isSelected}` on `RowContainer`. Implement roving tabindex (`0` on the focused row, `-1` elsewhere) plus arrow-key/Home/End handlers on the listbox container.

---

### TC9-03: `useAutoHide` and `useAPIHealthPoll` have no dedicated tests, and their sole caller's test never exercises their behavior
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/shared/useAutoHide.ts:1-24`, `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:1-77`
- **Status**: NEW
- **Description**: Both hooks were extracted from `ConnectionStatusIndicator` in #4186. Neither has a `__tests__` file; `ConnectionStatusIndicator.test.tsx` never uses fake timers and never exercises polling/latency state or the delayed-hide/cancel-on-unmount behavior. `useAPIHealthPoll` carries real accumulated subtlety — a mount-guard fix (#3585, dispatch-after-unmount race) and a visibility pause/resume fix (#3257) — neither currently guarded by any test.
- **Evidence**:
  ```ts
  // useAPIHealthPoll.ts:57-64 — visibility-driven pause/resume, #3257, untested
  const handleVisibility = () => {
    if (document.hidden) { stopPolling(); } else { pollHealth(); startPolling(); }
  };
  ```
- **Impact**: A regression in either hook (interval not clearing on unmount, mount-guard racing a fast unmount) would not be caught by any test — it would surface only as a live memory leak / dispatch-after-unmount warning, exactly how #3585 and #3257 were originally found.
- **Suggested Fix**: Add `hooks/shared/__tests__/useAutoHide.test.ts` and `useAPIHealthPoll.test.ts` with fake timers, asserting timer/interval firing, cancellation on unmount, and pause/resume across a `visibilitychange` dispatch.

---

### LOW

### C1-02: `useQueueKeyboardReorder.ts` and `QueuePanel.tsx` carry contradictory comments about row-key behavior
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/useQueueKeyboardReorder.ts:51-54,86-89`; `QueuePanel.tsx:39-60`
- **Status**: NEW
- **Description**: `QueuePanel.tsx` documents #4428's fix (index-free, occurrence-disambiguated row keys, replacing the old `${track.id}-${index}` scheme that forced unmount/remount on every reorder). `useQueueKeyboardReorder.ts` — extracted from the same file by #4916 — still justifies its focus-restoration effect with the **pre-fix** premise ("the row unmounts and remounts... key embeds the index, #4428"). With the current key scheme a reorder does not remount a row; `QueueTrackItem`'s memo comparator confirms the DOM node persists across reorders.
- **Impact**: No functional bug — the effect still works either way — but the comment is likely to mislead a future maintainer into thinking the `useLayoutEffect` indirection protects against a remount that no longer happens.
- **Suggested Fix**: Update the comment to describe the actual current reason (restoring focus after an *optimistic, possibly-reverted* reorder, re-deriving the DOM target after a props update) and note the still-live duplicate-track-id edge case if that's the real justification.

---

### R2-01: `cacheSlice.updateCache` is an eleventh dead slice action, missed by #4921's list
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/cacheSlice.ts:76-101`
- **Status**: NEW (sibling of open #4921, outside that issue's cited range)
- **Description**: `updateCache` has zero dispatch sites in production code. #4921 enumerated ten dead actions across all four slices, including `cacheSlice.ts:152-154`'s `resetCache` — but not `updateCache`, sitting earlier in the same file and equally unreachable.
- **Suggested Fix**: Fold into #4921's cleanup.

---

### R2-02: Four factory selectors and `selectFormattedQueueTime` in `queue.ts` have zero production consumers
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/selectors/queue.ts:38-45,110-134`
- **Status**: NEW
- **Description**: `makeSelectTrackAtIndex`, `makeSelectTracksInRange`, `makeSelectFilteredTracks`, `makeSelectTracksByDuration`, `selectFormattedQueueTime` are exported and barrel re-exported but never called from `hooks/`, `components/`, or `contexts/`. A distinct dead-code island from the already-tracked #4696 (the `performance/` toolkit) — these five never route through that barrel at all.
- **Suggested Fix**: Delete if no consumer is planned, or wire into the queue UI they appear built for (track-range virtualization, duration filters).

---

### R2-03: `errorTrackingMiddleware`'s `ErrorStore` is write-only; `getErrorStats`/`retryAction` are dead exports
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:183-226,311,375,437-458,467-487`
- **Status**: NEW (adjacent to open #4933/#4662 — those flag config fields with no implementation; this flags the class itself and two exported utilities)
- **Description**: `ErrorStore` is populated at two tracking sites but none of its four read methods is ever called, and the middleware closure has no way to hand the instance back to a caller. `getErrorStats()` and `retryAction()` are exported with zero external call sites.
- **Suggested Fix**: Wire `ErrorStore` into a debug/diagnostics surface, or delete it together with #4933/#4662's dead fields in one pass — same cleanup.

---

### T4-06: `queueService.ts`'s local `QueueTrack` inverts required/optional relative to the real backend `TrackInfo` contract
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/services/queueService.ts:17-24`
- **Status**: NEW (flagged as out-of-scope in the now-CLOSED #4787, never filed)
- **Description**: Local `QueueTrack` declares `filepath: string` required and `artist?`/`album?` optional — the exact inverse of the backend `TrackInfo` (`filepath` is `Field(exclude=True)`, never on the wire; `artist`/`album` are always-present required fields).
- **Impact**: Currently dead (`getQueue()`, the only function returning this type, has zero external callers). A landmine for any future code trusting `track.filepath`.
- **Suggested Fix**: Delete the local type and import `TrackInfo` from `@/types/websocket`, or correct the three fields.

---

### A6-04: A cluster of raw `fetch()` calls outside the shared HTTP layers has no request timeout
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `hooks/fingerprint/useAlbumFingerprint.ts:31`, `useTrackFingerprint.ts:31`, `useSimilarTracks.ts:174-182`, `components/library/Details/useAlbumDetails.ts:44-46,100-105`, `useArtistDetailsData.ts:38-40`, `EditMetadataDialog/useMetadataForm.ts:61-63,130-134`, `hooks/library/useLibraryScan.ts:74-79`, `useScanProgress.ts:80`, `useLibraryStats.ts:39`, `hooks/shared/useAPIHealthPoll.ts:30`
- **Status**: NEW (related to, but a disjoint file set from, Existing: #4694)
- **Description**: `apiRequest.ts` establishes `DEFAULT_TIMEOUT_MS = 30000` "so all three [HTTP layers] behave the same (#4442)." None of the ten sites above route through any of the three official layers — each calls `fetch()` directly with no timeout. Most wire an `AbortController` for unmount cancellation, so this is specifically a timeout gap, not (mostly) a cancellation gap.
- **Impact**: If the backend's ASGI loop stalls (a documented failure mode, #4815), any in-flight request from these sites hangs with no upper bound, leaving loading state stuck indefinitely. LOW because it requires an already-degraded backend, none are on the primary playback path, and several are best-effort/read-only.
- **Siblings**: #4694 already tracks the identical gap for `useAppDragDrop.ts` — not re-listed.
- **Suggested Fix**: Route through `apiRequest`'s `get`/`post` helpers instead of bare `fetch()`.

---

### P7-02: `paletteCache` (artwork color-extraction cache) grows unboundedly for the life of the session with no eviction
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/app/useArtworkPalette.ts:34`
- **Status**: NEW
- **Description**: Module-scope `Map<albumId, {revision, palette}>`, populated on every extraction, never pruned. Grows for every album ever viewed with palette extraction enabled — a larger, session-length-correlated set than the other module-scope caches in the same area.
- **Impact**: Each entry is small; not a meaningful concern even over a long session. Flagged as hardening, not a live problem.
- **Suggested Fix**: Not urgent. Cap with a simple LRU if addressed.

---

### Y8-01: Two `<h1>` elements render simultaneously on every library view
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:277-280`, `components/core/AppTopBar.styles.ts:57`, `components/library/Views/ViewContainer.tsx:63-76`
- **Status**: NEW (side effect of fixing 2026-07-29's Y8-02)
- **Description**: `014da248` changed `AppTopBar`'s `TitleBox` to `styled('h1')` to satisfy "no `<h1>` exists anywhere" — a premise that was already stale: `ViewContainer.tsx`'s `Typography component="h1"` (used by every library view) has rendered an `<h1>` since 2025-12-27, predating the audit that claimed none existed. The fix added a *second*, permanently-mounted `<h1>` with a hardcoded literal ("Your Music", never tracks `currentView`) in the `banner` landmark, alongside the pre-existing per-view `<h1>` in `<main>`. On mobile the top-bar heading is visually hidden but remains in the accessibility tree.
- **Impact**: A screen-reader user navigating by heading level lands on two unrelated level-1 headings with no structural relationship. Confusing, not broken (both landmarks are correctly labeled).
- **Suggested Fix**: Pick one canonical `<h1>`. Simplest: revert `TitleBox` to a non-heading element and keep `ViewContainer`'s per-view title as the sole `<h1>`; or drop `ViewContainer`'s heading to `<h2>` and make `AppTopBar`'s title track `currentView`.

---

## Relationships

**Cluster 1 — `PlaybackSessionContext` (#4541) shipped three independent defects in the same new file.**
H3-01 (command-drop race), P7-01 (10Hz re-render cascade), and TC9-02 (missing test-provider wrap) all trace to the same feature landing 2026-07-30 — one day after the last audit's baseline was cut. None is a duplicate of another: H3-01 is about *correctness* under concurrent input, P7-01 is about *performance* from the value-object shape, TC9-02 is about *test infrastructure* not keeping pace with production code. Because all three touch the same file and the same review pass will already have full context loaded, fixing them together (TC9-02 first, since it unblocks CI; then P7-01's context split, which naturally also gives H3-01 a cleaner place to key its pending-command state) is more efficient than three separate patches.

**Cluster 2 — accessibility fixes that closed the letter of the prior finding but not its intent (Y8-01, Y8-02).**
Both `014da248` changes (h1 heading, listbox role) satisfied their originating audit's literal wording while missing context the fix author didn't check for: an `<h1>` already existed elsewhere (Y8-01), and a real multi-select feature already existed under the newly-added listbox role (Y8-02). Same shape as the 2026-07-29 report's own Cluster 2 ("fixing at the call site rather than the choke point") — worth flagging in the fix-review process itself, not just these two instances.

**Cluster 3 — dead code as a recurring, ungated shape (R2-01, R2-02, R2-03, T4-06, A6-03's sibling list).**
Five more instances across three dimensions, continuing the 2026-07-29 report's Cluster 4 observation verbatim. No `knip`/`ts-prune` CI gate exists to stop this from regrowing every audit cycle.

**Cluster 4 — a dead type reintroducing a bug just fixed (A6-03), same failure mode as the already-fixed T4-02.**
Both are "the fix built its payload as an inline literal instead of importing/updating a named type, so the stale type silently survived the fix." Worth a lint rule or convention (require exported request/response types be the single source of truth a call site imports, not duplicates it can drift from) rather than fixing instance-by-instance.

---

## Prioritized Fix Order

1. **TC9-02** — one-line fix (add `PlaybackSessionProvider` to `AllProviders`), unblocks CI for every other PR, restores coverage for #4541's own tests. Do this first, before anything else in this list, since a red `master` gate affects unrelated work in progress.
2. **P7-01** — HIGH performance; the app-shell re-render affects the primary simultaneous-use case (browsing while listening). Do this while `PlaybackSessionContext.tsx` is already open from step 1.
3. **H3-01** — MEDIUM but same file; the context split from step 2 gives command-pending state a natural per-context home, so sequencing it right after is cheaper than a separate pass.
4. **A6-03** — delete the dead type immediately while A6-01's fix is fresh; near-zero effort, removes a real landmine.
5. **Y8-02** — the batch-actions multi-select feature is currently ARIA-broken for keyboard/screen-reader users; moderate effort (thread a prop, add roving tabindex).
6. **T4-05** — live race risk (blank artwork), moderate fix (extract and reuse the existing correct mapping from `usePlayerStateSync.ts`).
7. **C1-01** — cheap, well-understood fix (follow #3924's established extraction pattern) before the collapsed toggle is ever wired up for real.
8. **TC9-03** — add tests for `useAPIHealthPoll`'s two previously-fixed races (#3585, #3257) before either regresses silently again.
9. **Y8-01** — one-line-ish fix (drop the duplicate heading or make it track `currentView`).
10. **Remaining LOW** (C1-02, R2-01, R2-02, R2-03, T4-06, A6-04, P7-02) — opportunistic batch; consider filing a `knip`/`ts-prune` CI-gate issue at the same time to address Cluster 3 structurally instead of per-instance.
11. **#4877 (theme migration)** — not new, but update the tracked issue with this pass's re-measured count (88 files / 338 refs remaining, down from 103/324) and the newly-identified 11-file `design-system/primitives/` sub-list as the next slice.

---

## Verified, Not Reported

Recorded so future audits do not re-investigate. All confirmed fixed or confirmed still-accurately-tracked against current source (HEAD `06b9d0aa`) by the dimension agents:

**Fixed since 2026-07-29 (all re-verified in current source):**
- **C1-01/#4912** — dead `components/features/discovery/` tree deleted.
- **C1-02/#4880** — SettingsDialog/KeyboardShortcutsHelp now each wrapped in their own `ErrorBoundary`.
- **C1-03/#4916** — `QueuePanel.tsx` (275L) and `SimilarTracksModal.tsx` (198L) both now under 300 lines.
- **H3-01/#4885, H3-02, H3-03** — `useLibraryQuery.fetchMore` stale-response guard, `useLibraryPagination` shared in-flight-flag race, `useAlbumFingerprints` array mutation — all fixed.
- **P7-01 (prior)/`0c4fef28`** — GainNode leak fixed at the choke point (`cleanupStreaming()`), not per-call-site.
- **P7-02 (prior)/`3f25c0c5`** — track grid now right-sizes artwork via `withArtworkSize`.
- **A6-01, A6-02/#4854, #4859** — queue reorder and shuffle endpoint/payload contracts fixed, now regression-tested with literal URL/body assertions.
- **T4-01/#4896, T4-02/#4753** — `useRestAPI` gained opt-in runtime response validation; dead `AlbumDetailApiResponse` deleted.
- **Y8-01, Y8-02, Y8-03 (2026-07-29 numbering)** — role="listbox" ancestor added, `<h1>` added, view-change screen-reader announcement added — all landed, though Y8-01/Y8-02 in *this* report are the incompleteness gaps those same fixes left behind.
- **`fa13611b`** — sidebar `h2` labels, `PlaylistListHeader` keyboard support, `MediaCardOverlay` focus-visible overlay — all verified correct.
- **#4877 (design system)** — 5 named primitives (`Button`, `Input`, `IconButton`, `Badge`, `Slider`) plus `TrackRow.styles.ts`/`TrackTableRowItem.tsx` fully migrated to `themeVars`; count re-measured at 88 files remaining (down from 103) — issue kept open with updated scope, not re-filed.

**Confirmed still open, unregressed, not re-reported (already tracked):**
- **#4921** (ten dead slice actions — now eleven, see R2-01), **#4927** (`addTrack` positional-insert doesn't shift `currentIndex`), **#4933** (dead error-recovery config), **#4696** (`performance/` toolkit entirely dead), **#4660** (dead duplicate `nextTrack`/`previousTrack`), **#4662** (dead `errorActions` field) — Redux/middleware, zero commits to `store/` since 2026-07-29.
- **#4942** (duplicate `EnhancementPreset`), **#4949** (`ApiErrorHandler.parse` bypass), **#4461** (double-cast in `createCrudService`), **#4664** (29 production `any` occurrences, unchanged set), **#4680** (WS registry drift — `cache_cleared` now fixed, `job_progress`/`queue_updated` remain).
- **#4953** (relative import in `types/ws/streaming.ts`), **#4663** (35 raw-px spacing hits), **#4463** (`#7366f0` hex duplication), **#4392** (dead `focusManagement.ts` exports incl. off-brand hardcoded hex).
- **#4632** (Player's 10Hz tick re-renders six unmemoized children — narrower instance of P7-01 above), **#4697** (main chunk eagerly bundles heavy deps).
- **#4694** (`useAppDragDrop.ts` fetch calls lack timeout — A6-04 above is the disjoint remainder of this pattern).
- **#4474** (play/pause not announced to screen readers), **#4637** (no automated a11y testing), **#4473** (re-affirmed a third time: MUI Tooltip's `aria-label` injection makes this a non-issue).
- **#4965** (`deinterleaveToOutput` untested branches — TC9-01 from 2026-07-29, unchanged).
- **#4456, #4673** (component >300 lines census — `CozyAlbumGrid.tsx`, `ProgressBar.tsx`, `CozyLibraryView.tsx` still over; `Player.tsx` since dropped out of the set via an unrelated refactor).

**Swept clean, no findings (full list in each dimension's own report):**
WebSocket hook layer (connection, messages, errors, binary framing); `useAudioVisualization`, `useEnhancedStreamStart`/`useEnhancedSeek`/`useEnhancedPlayCommand`, `useEnhancementControl`, `useMasteringRecommendation`/`useFingerprintStatus`, `useAPIHealthPoll`'s visibility ordering, `useRestAPI`'s stale-response sequencing, `useOptimisticUpdate`/`useScanProgress`/`useArtworkUpdates`/`useQueueSubscription`/`usePlayerStateSync`/`usePlayTrack`/`usePlaybackQueue`; list virtualization (all 100+-item lists); image lazy-loading; WebSocket message-rate throttling; typography tokens; multi-level relative imports; `ClearQueueDialog`/`ProgressBar`/`VolumeControl`/`PlaybackControls` accessibility; contrast tokens and the theme-migration commit's lack of new hardcoded-color regressions; Redux slice test coverage; async/floating-promise discipline in new regression suites; global `WebSocketContext` unmock discipline (all 7 files that need it, correct).

---

*Generated by `/audit-frontend` on 2026-08-07. Next step: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-08-07.md`*
