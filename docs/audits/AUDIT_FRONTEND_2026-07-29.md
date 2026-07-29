# Frontend Audit — 2026-07-29

**Scope**: `auralis-web/frontend/` — components, Redux store, hooks, TypeScript types, design system, API clients, performance, accessibility, test coverage.
**Method**: 9 dimension agents, fresh read of current source. Deduplicated against 400 GitHub issues (open + closed) and the prior reports of 2026-07-12 / 2026-07-25.
**Depth**: deep. **Limit**: none.

---

## Executive Summary

**23 findings — 0 CRITICAL, 4 HIGH, 7 MEDIUM, 12 LOW.**

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 4 | A6-01, A6-02, P7-01, D5-01 |
| MEDIUM | 7 | C1-02, H3-01, H3-02, T4-01, T4-02, P7-02, Y8-01 |
| LOW | 12 | C1-01, C1-03, R2-01, R2-02, R2-03, H3-03, T4-03, T4-04, D5-02, Y8-02, Y8-03, TC9-01 |

### Verified baselines (not findings)

These were measured during this audit and are **healthy**. Do not file issues against them.

| Gate | Result |
|------|--------|
| `pnpm run type-check:prod` (`tsconfig.build.json`, CI-enforced) | **0 production errors** |
| `pnpm run type-check` (full, incl. tests) | 100 errors, **all in test files** — deliberately excluded from the CI gate by design (see #4665) |
| `pnpm run test:ci` + `pnpm run test:baseline` | **3261 passed, 165 failed, baseline cap 166 — "No new test failures"** |
| CI coverage | `.github/workflows/frontend-typecheck.yml` and `frontend-test.yml` both run. The old "no CI runs vitest" claim (#4640) is resolved. |

### Dimension coverage

All 9 dimensions declared in `.claude/commands/audit-frontend.md` were launched, completed, and persisted their output. **No dimension is unexamined.**

| # | Dimension | Status | Raw findings | Kept |
|---|-----------|--------|--------------|------|
| 1 | Component Quality | complete | 3 | 3 |
| 2 | Redux State | complete | 3 | 3 |
| 3 | Hook Correctness | complete | 4 | 3 |
| 4 | Type Safety | complete | 4 | 4 |
| 5 | Design System | complete | 2 | 2 |
| 6 | API Client | complete | 2 | 2 |
| 7 | Performance | complete | 2 | 2 |
| 8 | Accessibility | complete | 3 | 3 |
| 9 | Test Coverage | complete | 1 | 1 |
| | **Total** | | **24** | **23** |

One raw finding was dropped in merge: **H3-04** was the mandatory effect-cleanup sibling sweep, filed by its agent as "informational — verified, not a defect" (all three effects lacking cleanup were individually confirmed to correctly need none). It is recorded under *Verified, Not Reported* rather than counted as a finding. No cross-dimension duplicates were found; A6-01 and A6-02 share a file but are distinct functions.

### Caveats carried from the dimension agents

- **Dimension 7 (Performance)** deliberately dropped two candidate defects — a GainNode leak in `usePlayNormal.ts` and unbounded array growth in `useQueueHistory.ts` — after confirming neither hook has any live call site. These are real defects in genuinely dead code; if either hook is ever wired up, re-check both.
- **Dimension 3 (Hooks)** excluded two candidates as too speculative to survive its own disproof step: an `isLoading` race in `usePlaybackControl` and an overlapping-rollback race in `useQueueMutations`. Neither was reproduced against current call sites; both are unresolved rather than cleared.
- **Dimension 8 (Accessibility)** assessed color contrast by manual sRGB luminance computation, not by running an automated checker against rendered output. There is still no automated a11y test in the repo (#4637, open), so contrast and ARIA-tree conclusions rest on static reasoning.
- **Dimension 9 (Test Coverage)** did not run the full suite itself (the orchestrator's run is the authority). It relied on static analysis plus `test-baseline.json`.
- **Pre-existing test failures**: the 165 currently-failing specs are enumerated in `auralis-web/frontend/test-baseline.json` and the ratchet reported *"No new test failures."* No failing spec is reported as a finding anywhere in this report, and no case arose where pre-existing could not be distinguished from new — the baseline file made the distinction unambiguous.

### Key themes

1. **Two live REST calls have never worked.** The single largest theme this pass is not code quality — it is that `useQueueMutations` contains two endpoint-contract bugs that return HTTP 422 on every invocation (A6-01, A6-02). Both were verified against the real FastAPI app, not just by reading. Their unit tests pass because they mock `useRestAPI` wholesale and never assert the literal URL or body.
2. **Three previously-closed fixes are incomplete rather than regressed.** #4445 (GainNode disposal), #4447 (artwork size hints), and #4536 (keyboard queue reorder) each landed a real fix that does not cover the most-travelled call path. P7-01 and P7-02 are the direct sibling gaps; A6-01 silently invalidates #4536's shipped behavior.
3. **The theme migration is the widest-reaching user-visible defect.** 324 non-comment references across 103 production files still read the dark-only `tokens.colors.*` primitives instead of `themeVars`, against the contract stated in `ThemeContext.tsx` itself. This is documented as open work in `docs/audits/UI_THEME_UNIFICATION_2026-07-25.md` but is **not tracked by any GitHub issue**.
4. **The store and hook layers are in genuinely good shape.** Dimensions 2 and 3 — historically the richest source of findings — produced zero HIGH and zero MEDIUM (Redux) / two narrow MEDIUM races (hooks). The WebSocket transport, streaming core, and player-state sync were read in full and are heavily hardened with inline references to the issues that hardened them.
5. **Dead code keeps accumulating in directory-sized units.** A third orphaned component subtree (896 LOC) surfaced after two prior audits found two others, alongside ten never-dispatched Redux actions.

### Most impactful issues

- **A6-01** — queue reordering is completely non-functional through both the mouse and keyboard paths.
- **P7-01** — every Next/Previous click permanently leaks a connected `GainNode`.
- **D5-01** — light mode renders the library's primary content near-invisible.
- **A6-02** — the shuffle toggle 422s from the queue panel.

---

## Findings

## HIGH

### A6-01: Queue drag-and-drop AND keyboard reorder call the wrong endpoint — every reorder 422s
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:180-192` (called from `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx:189`)
- **Status**: NEW
- **Description**: `reorderTrack(fromIndex, toIndex)` sends `PUT /api/player/queue/reorder` with body `{from_index, to_index}`. That route's Pydantic model `ReorderQueueRequest` (`auralis-web/backend/routers/player.py:58-60`) accepts only `{new_order: list[int]}`, with no default — so FastAPI rejects the request during validation before any handler code runs. The single-item move the frontend actually wants lives at a **different** route, `PUT /api/player/queue/move` (`MoveQueueTrackRequest {from_index, to_index}`, `player.py:63-66,687-697`), whose model matches the sent payload exactly.
- **Evidence**:
  ```ts
  // useQueueMutations.ts:180-192
  const reorderTrack = useCallback(
    (fromIndex: number, toIndex: number): Promise<void> =>
      runOptimistic(
        () => dispatch(reduxReorderTrack({ fromIndex, toIndex })),
        () =>
          put('/api/player/queue/reorder', {   // <-- wrong route for this payload
            from_index: fromIndex,
            to_index: toIndex,
          }),
        'REORDER_ERROR'
      ),
  ```
  ```python
  # routers/player.py:58-60 — what /reorder actually requires
  class ReorderQueueRequest(BaseModel):
      new_order: list[int]

  # routers/player.py:63-66 — what the frontend is actually sending
  class MoveQueueTrackRequest(BaseModel):
      from_index: int
      to_index: int
  ```
  Verified against the live app: `PUT /api/player/queue/reorder {'from_index':0,'to_index':2}` → `422 body.new_order Field required`; the same payload to `/move` passes validation.
- **Impact**: Dragging a track to reorder the queue always fails. `runOptimistic` rolls back, so the row visibly snaps back to its original position with only a `console.error`. Critically, the keyboard-accessible reorder added by **#4536** (`handleKeyboardReorder`, `Alt+ArrowUp/Down`) routes through the exact same broken call — so the accessibility fix that closed #4536 has never actually worked end-to-end. Both interaction paths for queue reordering are dead.
- **Siblings**: None in the same file — `setQueue`/`addTrack`/`removeTrack`/`clearQueue`/`reorderQueue` all target correct routes with correct shapes. `useAppDragDrop.ts`'s `handleReorderQueue` uses `/api/player/queue/move` with the same `{from_index, to_index}` shape, confirming `/move` is the intended contract.
- **Related**: #4536 (its shipped fix is invalidated by this bug); A6-02 (same file, same class of drift).
- **Suggested Fix**: Change the call to `put('/api/player/queue/move', {from_index: fromIndex, to_index: toIndex})`. Add a unit test asserting the literal URL and body passed to `put` — the current tests mock `useRestAPI` entirely and cannot catch endpoint drift.

---

### A6-02: Shuffle toggle sends `enabled` as a query param; the backend requires it in the JSON body
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/player/useQueueMutations.ts:224-247`
- **Status**: NEW
- **Description**: `toggleShuffle()` calls `post('/api/player/queue/shuffle', undefined, {enabled: newShuffle})`. `useRestAPI.post`'s third argument is `queryParams` (`useRestAPI.ts:146-160`), and its body is `payload ? JSON.stringify(payload) : undefined` — so this issues `POST /api/player/queue/shuffle?enabled=true` with **no body at all**. The handler signature is `async def shuffle_queue(request: ShuffleRequest)` with no default, making the request body required; FastAPI returns `422 body Field required`. Backend commit `ac3f693a` (closing #3174) deliberately moved this parameter from query to body; the frontend caller was never updated, and still carries a now-false comment asserting the old contract.
- **Evidence**:
  ```ts
  // useQueueMutations.ts:234-237
  // Send enabled as query param — backend reads it as ?enabled=true/false   <-- stale since ac3f693a
  await post('/api/player/queue/shuffle', undefined, {
    enabled: newShuffle,
  });
  ```
  ```ts
  // useRestAPI.ts:158-160 — third arg is queryParams; body is omitted when payload is undefined
  body: payload ? JSON.stringify(payload) : undefined,
  ```
  ```python
  # routers/player.py:113-115,699-700
  class ShuffleRequest(BaseModel):
      enabled: bool = True
  async def shuffle_queue(request: ShuffleRequest) -> dict[str, Any]:
  ```
  Verified live: query-param-with-no-body → `422`; `json={}` → passes validation.
- **Impact**: Clicking shuffle in `QueuePanel.tsx:158` always fails. The optimistic `reduxSetIsShuffled` is rolled back and an `ApiError` surfaces. Shuffle is dead from this call site.
- **Siblings**: `queueService.shuffleQueue()` (`auralis-web/frontend/src/services/queueService.ts:88-90`) sends a real JSON body and works — the same endpoint has one working and one broken client. The JSDoc example at `auralis-web/frontend/src/hooks/api/useRestAPI.ts:144` documents this now-wrong query-param pattern and is the only in-repo example of the `queryParams` argument, so it will seed the same mistake again.
- **Related**: A6-01 (same file); #4693 (three parallel HTTP layers).
- **Suggested Fix**: Change to `post('/api/player/queue/shuffle', {enabled: newShuffle})`, matching `queueService.shuffleQueue`'s already-correct pattern. Delete the stale comment and fix the misleading `useRestAPI` docblock example.

---

### P7-01: Every Next/Previous click leaks a connected GainNode — `cleanupStreaming()` nulls the engine ref without disposing it
- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:174-192` (`cleanupStreaming`), `:447-453` (`stopPlayback`); reached from `auralis-web/frontend/src/components/player/Player.tsx:109,133`
- **Status**: Regression of #4445 (incomplete fix — the most frequently hit path was missed)
- **Description**: `AudioPlaybackEngine.dispose()` exists precisely because `gainNode` is wired permanently in the constructor (`gainNode → analyser → destination`) and is never otherwise disconnected; its own docstring says so. In enhanced mode the `AudioContext` stays open across track switches (`closeContextOnCleanup: false`, `usePlayEnhanced.ts:140`), so an engine that is dropped without `dispose()` strands its gain node for the life of the context. #4445 wired `dispose()` into exactly two places — `useEnhancedStreamStart.ts:128` (before constructing the next engine) and `usePlayEnhanced.ts:176` (unmount). It did **not** add one to `cleanupStreaming()` in the shared core, which sets `playbackEngineRef.current = null` directly. `Player.tsx`'s Next/Previous handlers call `stopPlayback()`, which invokes `playbackEngineRef.current?.stopPlayback()` (tears down the worklet/script processor only — not the gain node) and then `cleanupStreaming()`. By the time the next track's `audio_stream_start` arrives, `useEnhancedStreamStart`'s dispose guard sees a `null` ref and no-ops.
- **Evidence**:
  ```ts
  // useAudioStreamingCore.ts:174-182
  const cleanupStreaming = useCallback(() => {
    clearStreamStartWatchdog();
    abortRef.current?.abort();
    pcmBufferRef.current?.dispose();      // buffer IS disposed
    pcmBufferRef.current = null;
    playbackEngineRef.current = null;     // engine is NOT — no dispose() call
  ```
  ```ts
  // useAudioStreamingCore.ts:447-453
  playbackEngineRef.current?.stopPlayback();   // processor only, per AudioPlaybackEngine docstring
  dispatch(resetStreaming(streamType));
  cleanupStreaming();                          // nulls the ref without disposing
  ```
  ```ts
  // useEnhancedStreamStart.ts:126-128 — the #4445 guard, now unreachable after a stop
  // "...so a stranded gainNode..."
  core.playbackEngineRef.current?.dispose();   // ref is already null here
  ```
  Confirmed: the only production `dispose()` call sites on `playbackEngineRef` are `useEnhancedStreamStart.ts:128` and `usePlayEnhanced.ts:176`; `cleanupStreaming` has none.
- **Impact**: Every manual skip during enhanced playback (the only live playback path) permanently leaks one `GainNode` still connected to the shared analyser → destination graph, unreachable by any JS reference. Skipping is among the most frequent interactions in a music player; a long session with heavy skipping accumulates dozens to hundreds of live nodes, degrading Web Audio graph performance and defeating #4445 for exactly the interaction it was meant to cover.
- **Siblings**: `handleStreamError` (`useAudioStreamingCore.ts:373-383`) calls `cleanupStreaming()` directly and hits the identical path. Any caller reaching `cleanupStreaming()` while `closeContextOnCleanup: false` is affected.
- **Related**: #4445.
- **Suggested Fix**: Call `playbackEngineRef.current?.dispose()` inside `cleanupStreaming()` before nulling the ref. `dispose()` is documented idempotent, so this is safe alongside the existing two call sites and closes `stopPlayback()`, `handleStreamError()`, and any future caller in one change.

---

### D5-01: 103 production files still read dark-only color primitives instead of `themeVars` — light mode is unreadable across the library
- **Severity**: HIGH
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts:175,187,199,218,238`; `auralis-web/frontend/src/components/library/Items/tables/TrackTableRowItem.tsx:79,88,96,113`; `auralis-web/frontend/src/components/playlist/PlaylistList.styles.ts:45,105,128,144,161`; `auralis-web/frontend/src/components/library/Details/ArtistDetailHeader.tsx:34`; `auralis-web/frontend/src/components/library/Items/albums/RecentlyTouchedSection.tsx:110` (+98 more files)
- **Status**: NEW
- **Description**: `auralis-web/frontend/src/contexts/ThemeContext.tsx:13-17` states the contract explicitly: "`themeVars` (and the `--app-*` CSS variables this provider writes) is the only theme-aware colour source. The raw `tokens.colors.*` primitives remain dark-only build blocks and are not for direct component use." `tokens.colors.text.primary/secondary/metadata/disabled` (`auralis-web/frontend/src/design-system/tokens/colors.ts:98-119`) are hardcoded `rgba(255,255,255,…)` with no light-mode branch. A repo-wide sweep (comments excluded) finds **324 direct references across 103 production files**, including the design-system primitives themselves (`Button.tsx`, `Input.tsx`, `IconButton.tsx`, `Badge.tsx`, `Slider.tsx`). `TrackRow.styles.ts`'s `RowContainer` resolves to `background: 'transparent'` for non-current rows, so in light mode the row inherits the light page background while its title/artist/album/duration text stays near-white.
- **Evidence**:
  ```ts
  // design-system/tokens/colors.ts:98-105 — no light-mode branch
  text: {
    primary: 'rgba(255, 255, 255, 0.95)',
    secondary: 'rgba(255, 255, 255, 0.68)',
  ```
  ```ts
  // components/library/Items/tracks/TrackRow.styles.ts
  export const TrackTitle = styled(Typography)<{ iscurrent?: string }>(({ iscurrent }) => ({
    color: tokens.colors.text.primary,   // never theme-aware
  ```
  ```
  $ grep -r "tokens\.colors\.text" src --include=*.tsx --include=*.ts \
      | grep -v __tests__ | grep -v '\.test\.' | grep -vE ':\s*(\*|//|/\*)'
  324 references across 103 files
  ```
  Light-mode background is `#F8F9FD` (`colors.ts:257`), against which `rgba(255,255,255,0.95)` text is effectively invisible.
- **Impact**: The primary content of the library, queue, playlist, and search views becomes unreadable whenever a user toggles to light mode using the shipped `ThemeToggle`. This is the widest-reaching user-visible defect found in this audit.
- **Siblings**: The same pattern spans `AlbumTrackTable.tsx`, `TrackTableHeader.tsx`, `AlbumDetailView.tsx`, `AlbumMetadata.tsx`, `ArtistDetailTabs.tsx`, `DroppablePlaylist.styles.ts`, `EditPlaylistDialog.styles.ts`, `CreatePlaylistDialog.styles.ts`, `PlaybackControlsStyles.ts`, `ProgressBar.styles.ts`, `QueueStatisticsPanel.styles.ts`, and the whole `components/features/discovery/` tree (itself dead — see C1-01). `theme/semanticTheme.ts`'s own 9 references are legitimate; it is the mapping layer.
- **Related**: #4534 and #4535 were both re-verified as **still fixed and now regression-test-guarded** (`theme/__tests__/cssCustomPropertyProducers.test.ts`) — this is the untracked remainder of the same class of bug, not a regression of either. `docs/audits/UI_THEME_UNIFICATION_2026-07-25.md` documents this migration as deliberately incomplete ("repository-wide migration remains open"), but no GitHub issue tracks the remaining work.
- **Suggested Fix**: Replace `tokens.colors.text.*` / `tokens.colors.bg.*` in these `styled()` definitions with the corresponding `themeVars.textPrimary/textSecondary/textMuted/…` so colors resolve through the `--app-*` custom properties `ThemeContext` already publishes. Prioritize `TrackRow` and `TrackTableRowItem` (highest reach), then the design-system primitives, since fixing those propagates to every consumer. File a tracking issue so the remainder is not invisible to the backlog.

---

## MEDIUM

### C1-02: SettingsDialog and KeyboardShortcutsHelp have no local ErrorBoundary — a render crash there unmounts the whole app including playback
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:332-352`; `auralis-web/frontend/src/components/settings/SettingsDialog.tsx`; `auralis-web/frontend/src/components/shared/KeyboardShortcutsHelp.tsx`
- **Status**: NEW
- **Description**: `ComfortableApp.tsx` wraps the library subtree and the `<Player />` subtree each in its own `ErrorBoundary` with a graceful fallback (documented at lines 294-296 and 354-356, referencing #3583 and #3115) precisely so a crash in one does not kill the others. `SettingsDialog` and `KeyboardShortcutsHelp` are mounted as plain siblings inside `<Suspense fallback={null}>` with no boundary of their own. `Suspense` does not catch render errors — only an `ErrorBoundary` does.
- **Evidence**:
  ```tsx
  // ComfortableApp.tsx:332-342 — no ErrorBoundary
  <Suspense fallback={null}>
    <SettingsDialog open={settingsOpen} onClose={...} onSettingsChange={...} />
  </Suspense>
  ```
  Compare `ComfortableApp.tsx:298-324` (Library) and `:358-375` (Player), each with a scoped fallback.
- **Impact**: A user opens Settings mid-playback; if any of the six settings-tab panels throws during render (e.g. a malformed persisted setting hitting `.map`/`.toFixed`), the exception propagates to the single root boundary in `index.tsx`, unmounting the entire app — sidebar, top bar, library, and the actively-playing `<Player />` together. Strictly worse than the two subtrees deliberately hardened against exactly this.
- **Siblings**: None — Library and Player are both covered; this is the only gap.
- **Suggested Fix**: Wrap each in its own `<ErrorBoundary fallback={...}>` following the existing #3583 / #3115 pattern, with a fallback that at minimum lets the dialog close without affecting the rest of the app.

---

### H3-01: `useLibraryQuery`'s `fetchMore` has no stale-response guard, unlike `executeQuery`
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:208,287-362,368-404`
- **Status**: NEW
- **Description**: `executeQuery` guards every state write with `requestIdRef`/`isStale()` — added by #4609 to stop an older search's response from clobbering a newer one. `fetchMore` (infinite-scroll pagination) was never brought under the same guard: it checks `isFetchingMoreRef` / `hasMore` / `isFetchingRef` *before* issuing the request and never re-checks staleness after the `await` resolves.
- **Evidence**:
  ```ts
  // executeQuery — guarded (304-317)
  const myRequestId = ++requestIdRef.current;
  const isStale = () => requestIdRef.current !== myRequestId;
  if (isStale()) { return; }

  // fetchMore — unguarded (368-404)
  const response = await get<LibraryQueryResponse<T>>(buildEndpoint(nextOffset));
  if (response) {
    setOffset(nextOffset);
    setData(prev => [...prev, ...items]);   // no isStale() check
  }
  ```
- **Impact**: A user scrolls (starting `fetchMore`) and then changes the search term before it resolves. The pre-flight `isFetchingRef` check only covers whether an `executeQuery` was in flight *at start*; it does not stop the late response from mutating `data`/`offset` after a newer `executeQuery` has already replaced `data`. Result: the new query's page 1 followed by an appended page 2 from the superseded query — visibly wrong tracks under a new search term.
- **Siblings**: None — `useInfiniteAlbums.ts` uses TanStack `useInfiniteQuery`, which owns its own cancellation.
- **Related**: #4609 (fixed `executeQuery` only); H3-02.
- **Suggested Fix**: Have `fetchMore` claim a `requestIdRef` id the same way `executeQuery` does, or route it through `executeQuery(nextOffset, true)` which already owns the guard, rather than maintaining a second unguarded fetch path.

---

### H3-02: `useLibraryPagination` shares one in-flight flag between `fetchTracks` and `loadMore`, so a view-change refetch silently no-ops
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:33-34,53-121,123-179`
- **Status**: NEW
- **Description**: `fetchTracks` (mount / `view` change, via `useLibraryWithStats.ts`) and `loadMore` (infinite scroll) both gate on the *same* `fetchInProgressRef` boolean and bail with no retry or queueing when it is already `true`. Scrolling and switching views are independent user actions, so `loadMore` can be mid-flight from the previous view exactly when the view switches.
- **Evidence**:
  ```ts
  const fetchInProgressRef = useRef(false);   // single flag, shared by both

  const fetchTracks = useCallback(async (resetPagination = true) => {
    if (fetchInProgressRef.current) { return; }   // silently drops the refresh
  }, [view]);

  const loadMore = useCallback(async () => {
    if (fetchInProgressRef.current) { return; }
    fetchInProgressRef.current = true;
    setTracks((prev) => [...prev, ...transformedTracks]);   // appends using the OLD `view` closure
  }, [view]);
  ```
- **Impact**: User scrolls "All Tracks" (loadMore in flight) then switches to another tab. `fetchTracks()` for the new view bails immediately, so `tracks`/`offset`/`hasMore` are never reset. When the stale `loadMore` resolves it appends the *old* view's next page onto the still-displayed old list while the tab state claims a different view. No effect re-triggers a retry, so the wrong content persists until a later view change happens to land while nothing is in flight.
- **Siblings**: None — unique to this hook. `useLibraryQuery.ts` uses separate refs but still has the H3-01 gap.
- **Related**: H3-01.
- **Suggested Fix**: Give `loadMore` its own in-flight flag (an `isLoadingMore` state already exists separately), or have `fetchTracks` abort/supersede an in-flight `loadMore` (it already manages `fetchAbortRef`) instead of returning early.

---

### T4-01: `useRestAPI` casts every parsed response to `T` with zero runtime validation
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:118-119,173-174,221-222,269-270`
- **Status**: NEW
- **Description**: #4607 (CLOSED) added a `validate` option to `apiRequest()` specifically because `Response.json()` resolves to `any`, making every `as T` a compile-time-only contract that lets backend field drift surface as a downstream `undefined`/`NaN` far from its cause. That fix was never extended to the sibling HTTP layer: all four verbs in `useRestAPI` do the same unguarded `const data = await response.json(); return data as T;` with no validation hook at all.
- **Evidence**:
  ```ts
  // hooks/api/useRestAPI.ts:118-119 (get) — identical at post/put/patch
  const data = await response.json();
  return data as T;
  ```
  ```ts
  // utils/apiRequest.ts:60-69 — the guard added by #4607, present only here
  validate?: (value: unknown) => boolean;
  ```
- **Impact**: `useRestAPI()` backs `usePlaybackControl`, `useLibraryQuery`, `useEnhancementControl`, `useQueueHistory`, `useQueueMutations`, and `useQueueFetch` — the player, library-browsing, and queue critical paths. A renamed or dropped backend field on any of these (the exact class of bug #3593/#3976/#4440/#4441 all were) is not caught at the boundary; it silently becomes `undefined` deep in a component. A6-01 and A6-02 are the live proof that this layer's endpoint contracts do drift undetected.
- **Siblings**: #4693 (three parallel HTTP layers, of which only one received the #4607 guard).
- **Related**: #4607, #4693, A6-01, A6-02.
- **Suggested Fix**: Either migrate `useRestAPI`'s callers onto `apiRequest` (retiring the duplicate layer per #4693's direction), or add the same optional `validate?: (value: unknown) => boolean` parameter and wire the existing `responseGuards.ts` guards into the call sites that already have one.

---

### T4-02: `AlbumDetailApiResponse` is dead AND shape-drifted from the endpoint it names
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/api/transformers/types.ts:145-147`
- **Status**: NEW
- **Description**: `AlbumDetailApiResponse extends AlbumApiResponse` and declares an all-snake_case shape (`track_count`, `artwork_url`, `total_duration`, plus `tracks`). It is exported through the `@/api/transformers` barrel but has zero import sites anywhere in `src/`. It also no longer describes the endpoint its name implies: `GET /api/albums/{id}` is served by `serialize_album_detail()` (`auralis-web/backend/routers/serializers.py:227-248`), which — per its own #4423 docstring — deliberately returns the **camelCase** domain shape (`trackCount`/`artworkUrl`/`totalDuration`/`artistId`).
- **Evidence**:
  ```ts
  // api/transformers/types.ts:145-147
  export interface AlbumDetailApiResponse extends AlbumApiResponse {
    tracks: TrackApiResponse[];
  }
  ```
  ```python
  # routers/serializers.py:227-235
  def serialize_album_detail(album: Any) -> dict[str, Any]:
      """Serialize an album to the frontend camelCase domain shape (#4423)."""
  ```
- **Impact**: No runtime path exercises it today, but it is publicly exported and is the obvious thing to reach for if a future feature needs album-detail data. Anyone who does gets a type asserting snake_case fields against a camelCase payload, producing silent `undefined`s — exactly the class of bug #4423/#4568 were filed to fix.
- **Siblings**: Same family as #4460/#4398 (dead/drifted types in `types/api.ts`), but this one lives in `api/transformers/types.ts` and was not covered by those.
- **Suggested Fix**: Delete it (no importers), or redeclare it as the camelCase `Album & { tracks: DetailTrack[] }` shape `serialize_album_detail` actually returns.

---

### P7-02: Track grid view requests full-resolution artwork for small thumbnails
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/track/TrackCard.tsx:40-58`, consumed by `auralis-web/frontend/src/components/library/Views/TrackGridView.tsx:107-117`
- **Status**: NEW (sibling gap — #4447's fix never touched this call site)
- **Description**: #4447 added a `size` hint (`getArtworkUrl`/`withArtworkSize`) so the backend serves a downscaled, cache-bucketed thumbnail. It was applied to `AlbumCard.tsx` (`size: 256`), `AlbumArt.tsx`, `useArtworkPalette.ts` (`size: 64`), and the list-view `TrackRow.tsx` (`withArtworkSize(..., 80)`). `TrackCard.tsx` — used by `TrackGridView`, the grid layout for the main track library view — passes `track.artworkUrl` straight through with no size hint.
- **Evidence**:
  ```ts
  // TrackCard.tsx:40-58 — no withArtworkSize() anywhere
  <MediaCard variant="track" ... artworkUrl={albumArt} ... />
  ```
  ```ts
  // components/library/Items/tracks/TrackRow.tsx:101 — the already-fixed list-view sibling
  const rowArtworkUrl = withArtworkSize(track.artworkUrl ?? undefined, 80);
  ```
- **Impact**: Switching the library to grid view downloads and decodes full-resolution embedded artwork (several MB for high-res FLAC covers) to display at ~216px. Native `loading="lazy"` limits it to visible cards, but each is still oversized — increasing bandwidth, decode cost, and memory per scroll versus the equivalent already-fixed list view.
- **Siblings**: None — `AlbumGridContent.tsx`/`CozyAlbumGrid.tsx` already pass `size: 256` via `AlbumCard`; only the track-card grid path was missed.
- **Related**: #4447.
- **Suggested Fix**: Add a `size` prop to `TrackCard` mirroring `AlbumCard`, applying `withArtworkSize(albumArt, 216)` (matching `TrackGridView`'s `MIN_COLUMN_WIDTH`) before passing to `MediaCard`.

---

### Y8-01: Track list rows use `role="option"` with no `role="listbox"` ancestor
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:105-123`, `auralis-web/frontend/src/components/library/Views/TrackListViewContent.tsx:92-134`, `auralis-web/frontend/src/components/library/Views/TrackListView.styles.ts:5`
- **Status**: NEW
- **Description**: Every row in the virtualized track list declares `role="option"`, but per WAI-ARIA `option` is only valid as a descendant of `role="listbox"` (or `grid`/`select`/`combobox` popup). No such ancestor exists: the virtualizer wraps rows in plain `<div>`s and `ListViewContainer` is a bare `styled(Paper)` with no role. This is an `aria-required-parent` violation that axe-core flags directly.
- **Evidence**:
  ```tsx
  // TrackRow.tsx:105-107
  <RowContainer tabIndex={0} role="option" aria-label={`${track.title} by ${track.artist}`}>
  ```
  ```tsx
  // TrackListViewContent.tsx:93-134 — no role between container and rows
  <ListViewContainer elevation={2}>
    <div ref={listContainerRef}>
      <div style={{ height: virtualizer.getTotalSize() }}>
  ```
- **Impact**: Screen readers receive a malformed accessibility tree for the primary library-browsing view. Orphaned `option` roles are handled inconsistently — some AT drop the role entirely, others fail to announce set size/position ("3 of 240") — degrading the core browse experience even though rows remain individually focusable.
- **Siblings**: `role="option"` appears only in this file repo-wide, so one fix closes the gap.
- **Suggested Fix**: Add `role="listbox"` plus an `aria-label` (e.g. "Track list") to the virtualizer/scroll container in `TrackListViewContent.tsx` or to `ListViewContainer`.

---

## LOW

### C1-01: `components/features/discovery/` is a dead 13-file tree duplicating the live SimilarTracksModal feature
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/features/discovery/` (896 LOC across non-test files)
- **Status**: NEW
- **Description**: The entire directory — a "similar tracks" list and a "similarity dimensions" visualization, each cleanly split into loading/error/empty/list sub-components — has zero importers outside its own `__tests__`. The feature it implements is live through a completely different, independently written path: `components/shared/SimilarTracksModal/SimilarTracksModal.tsx`, wired into `CozyLibraryView.tsx` and `AlbumDetailView.tsx`, backed by `hooks/fingerprint/useSimilarTracks.ts`. The two share no code (dead tree uses `useSimilarTracksLoader`/`useSimilarTracksFormatting`; the live modal uses `useSimilarTracks`).
- **Evidence**:
  ```
  $ grep -rln "features/discovery" --include="*.tsx" --include="*.ts" src | grep -v "components/features/discovery/"
  src/components/__tests__/SimilarityVisualization.test.tsx
  src/components/__tests__/SimilarTracks.test.tsx
  ```
  No barrel consumer, no route, no `lazy()` reference, no dynamic-import string elsewhere in `src/`.
- **Impact**: ~900 lines of maintained-looking, tested, fully dead production code. Anyone touching similarity logic risks fixing the wrong copy — which has already happened once (#4579 found the sibling `enhancement/` and `enhancement-pane/` dead trees by the same pattern). This is a third instance that pass missed.
- **Siblings**: #4579 (`components/enhancement/`, `components/enhancement-pane/`).
- **Related**: D5-01 (this tree is also a `tokens.colors.*` offender, so deleting it shrinks that migration).
- **Suggested Fix**: Delete the directory and its tests. If the 25D dimension visualization is wanted, port it as a sub-view of the live `SimilarTracksModal` rather than resurrecting the orphan.

---

### C1-03: Two more actively-rendered components exceed the 300-line guideline, uncovered by the tracking issue
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx` (391 lines); `auralis-web/frontend/src/components/shared/SimilarTracksModal/SimilarTracksModal.tsx` (351 lines)
- **Status**: NEW (extends Existing: #4456)
- **Description**: #4456 names `CozyAlbumGrid.tsx` (390L), `Player.tsx` (335L), `ProgressBar.tsx` (331L), and `CozyLibraryView.tsx` (306L) — not these two, both currently over the limit and both live, frequently-touched components. `QueuePanel` mixes six distinct concerns: list rendering, virtualization, mouse drag-and-drop, keyboard reorder, drag auto-scroll, post-reorder focus restoration, and a clear-queue confirmation flow.
- **Evidence**:
  ```
  391 components/player/QueuePanel/QueuePanel.tsx
  390 components/library/Items/albums/CozyAlbumGrid.tsx
  351 components/shared/SimilarTracksModal/SimilarTracksModal.tsx
  ```
- **Impact**: Maintainability only.
- **Siblings**: #4456 tracks the other four.
- **Suggested Fix**: Batch into #4456 or the #4075-4083 god-file-split series. For `QueuePanel`, extract `useQueueAutoScroll` (the RAF drag-scroll loop) and `useQueueKeyboardReorder` (reorder + focus restoration).

---

### R2-01: Ten slice actions across all four slices are never dispatched from production code
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:236-238,243-279,284-292,435-451`; `auralis-web/frontend/src/store/slices/queueSlice.ts:298-300,333-335`; `auralis-web/frontend/src/store/slices/cacheSlice.ts:152-154`; `auralis-web/frontend/src/store/slices/connectionSlice.ts:125-127,152-171,176-178`
- **Status**: NEW
- **Description**: Ten of ~40 exported actions have zero dispatch sites outside their own definitions/exports and unit tests: `updatePlaybackState`, `updateStreamingInfo`, `resetPlayer`, `player.clearError`, `resetQueue`, `queue.clearError`, `resetCache`, `updateConnectionState`, `resetConnection`, `setMaxReconnectAttempts`. The `updatePlaybackState`/`updateStreamingInfo`/`updateConnectionState` trio is the notable part: each is doc-commented "for WebSocket sync" and carries substantial historically-patched logic (streaming deep-merge, `currentTime`/`duration` clamping, undefined-filtering — fixes #2352, #3025, #4191, #2774). But the actual sync hook `usePlayerStateSync.ts` dispatches only field-level actions and never calls them; `useAPIHealthPoll.ts` likewise dispatches `setWSConnected`/`setAPIConnected`/`setLatency` directly.
- **Evidence**:
  ```
  $ grep -rn "\bupdatePlaybackState\b" src | grep -v "__tests__\|\.test\."
  store/slices/playerSlice.ts:243:    updatePlaybackState: {
  store/slices/playerSlice.ts:467:  updatePlaybackState,
  ```
  (definition + export only; same for the other nine)
- **Impact**: No runtime risk, but real maintenance cost: four historical bug-fix commits hardened a codepath the app never executes, and the extensive tests for these reducers give false confidence that "WebSocket sync" is covered when the real sync hook uses a separate, independently hardened set of dispatches.
- **Siblings**: #4660 (`nextTrack`/`previousTrack` dead duplicate), #4662 (`errorActions` dead config) — this is the remaining, larger cluster of the same defect.
- **Suggested Fix**: Delete the bulk-update/reset actions and their tests if field-level dispatch is the intended architecture; otherwise add a comment on `usePlayerStateSync.ts`/`useAPIHealthPoll.ts` noting they exist and are unused, so the next refactor does not duplicate the logic a third time.

---

### R2-02: `queueSlice.addTrack`'s positional-insert branch does not shift `currentIndex`
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:56-69`
- **Status**: NEW (distinct from #4483, which flags the branch only as untested)
- **Description**: `addTrack(track, position)` splices into `state.tracks` at an arbitrary `position` but never adjusts `state.currentIndex`. If `position <= currentIndex`, every track from `position` onward shifts right, so `currentIndex` now points at the *newly inserted* track. Every other index-mutating reducer here (`removeTrack`, `reorderTrack`) explicitly re-derives `currentIndex` after its splice; `addTrack` is the lone exception.
- **Evidence**:
  ```ts
  if (pos !== undefined && pos >= 0 && pos <= state.tracks.length) {
    state.tracks.splice(pos, 0, action.payload);   // currentIndex untouched
  } else {
    state.tracks.push(action.payload);
  }
  ```
  Contrast `reorderTrack` (lines 130-137), which recomputes `currentIndex` after every splice pair.
- **Impact**: Currently dormant — the `position` parameter has zero production callers (the only `useQueue()` consumers use append-only `.addMany()`). If a "play next" / "insert at position" feature is ever wired here, `selectCurrentQueueTrack` would silently report the wrong now-playing track.
- **Siblings**: #4483 (same reducer/branch, test-coverage only — this is the functional bug that missing test would have caught).
- **Suggested Fix**: Mirror `reorderTrack`: after splicing, `if (pos <= state.currentIndex) state.currentIndex += 1;`.

---

### R2-03: `errorTrackingMiddleware`'s advertised recovery feature has no implementation
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:56,59,177`
- **Status**: NEW (sibling to open #4662)
- **Description**: The module docblock lists "Recovery action suggestions" as a feature, and `ErrorTrackingConfig` declares `onRecovery?: (error: TrackedError) => void` and `recoveryStrategies?: Map<string, () => Record<string, unknown>>` (defaulted to `new Map()`). Neither is ever read in the middleware body — only `onError` is invoked. No lookup into `recoveryStrategies`, no call to `onRecovery`.
- **Evidence**:
  ```
  $ grep -n "onRecovery\|recoveryStrategies" store/middleware/errorTrackingMiddleware.ts
  56:  onRecovery?: (error: TrackedError) => void;
  59:  recoveryStrategies?: Map<string, () => Record<string, unknown>>;
  177:  recoveryStrategies: new Map(),
  ```
  No third occurrence; the dispatch body (245-393) handles only `onError`.
- **Impact**: A consumer passing either field expecting recovery hooks to fire gets a silent no-op — the same failure mode already documented for `errorActions` in #4662, two more fields in the same struct.
- **Siblings**: #4662 (same file, same class).
- **Suggested Fix**: Wire `recoveryStrategies.get(category)?.()` + `onRecovery` into the success path, or drop both fields and the doc claim. Fix together with #4662.

---

### H3-03: `useAlbumFingerprints` mutates the caller's `albumIds` array in place via `.sort()`
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:104-106`
- **Status**: NEW
- **Description**: The query key is built as `albumIds.sort().join(',')`. `Array.prototype.sort()` sorts in place and returns the same reference — it does not copy. Both call sites pass a `useMemo`-cached array (`CozyAlbumGrid.tsx:78`, `RecentlyTouchedSection.tsx:88`), so the hook mutates a value it does not own, on every render, as a side effect of computing a cache key.
- **Evidence**:
  ```ts
  queryKey: ['album-fingerprints-batch', albumIds.sort().join(',')],  // mutates caller's array
  ```
- **Impact**: Inert today — neither call site reads `albumIds` again after passing it (render order comes from separately-copied arrays). It is nonetheless a real purity violation: any future caller reusing the reference for render order, an effect dependency, or an order-sensitive check would see it silently reordered.
- **Siblings**: None — no other reviewed hook mutates an array argument.
- **Suggested Fix**: `queryKey: ['album-fingerprints-batch', [...albumIds].sort().join(',')]`.

---

### T4-03: `EnhancementPreset` is declared twice with structurally incompatible shapes
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/api.ts:180-186`, `auralis-web/frontend/src/types/domain.ts:169-174`
- **Status**: NEW
- **Description**: Two unrelated types share the name `EnhancementPreset`: `types/domain.ts` declares the string-literal union used as the settings *value*, while `types/api.ts` independently declares an object interface `{id, name, description, icon?, is_default}` — a preset *descriptor* for the `/api/enhancement/presets` list endpoint.
- **Evidence**:
  ```ts
  // types/domain.ts:169-174
  export type EnhancementPreset = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  ```
  ```ts
  // types/api.ts:180-186
  export interface EnhancementPreset { id: string; name: string; description: string; icon?: string; is_default: boolean; }
  ```
- **Impact**: No live bug — every consumer imports the specific module path it needs, so resolution is unambiguous today. But this is exactly the anti-pattern `domain.ts:91-102` documents as already-solved for `PlayerState` ("Three same-named types meant an IDE would autocomplete whichever it found first"). An editor auto-import on a bare reference can silently pick the wrong one.
- **Siblings**: The fixed `PlayerState` triplication.
- **Suggested Fix**: Rename the `types/api.ts` descriptor to `EnhancementPresetInfo` — it is already distinct in shape and purpose.

---

### T4-04: `ApiErrorHandler.parse` bypasses its own `isApiError` guard with a weaker cast
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/api.ts:39-48,375-377`
- **Status**: NEW
- **Description**: `types/api.ts` defines a proper structural guard `isApiError` that checks `typeof status === 'number'` and `typeof message === 'string'`. `ApiErrorHandler.parse` — used everywhere errors are normalized (`usePlaybackControl`, `useRestAPI`, `useQueueMutations`, `useLibraryQuery`, `useQueueHistory`, `useEnhancementControl`) — does not call it, re-implementing a weaker inline `in`-operator check with no value type-checking, then casting unchecked.
- **Evidence**:
  ```ts
  // types/api.ts:375-377
  if (typeof error === 'object' && error !== null && 'status' in error && 'message' in error) {
    return error as ApiError;
  }
  ```
  vs. the unused guard 330 lines above it, which additionally checks `typeof (err as ApiError).status === 'number'`.
- **Impact**: An object with `status: "500"` (string) passes and is returned as a well-typed `ApiError`. Downstream `ApiErrorHandler.isNetworkError`'s `error.status >= 500` then silently misbehaves instead of falling through to the safe default. Low likelihood — most callers throw real `Error` instances, caught by the branch above — but two contradictory checks in one file is easy to miss.
- **Siblings**: Distinct from #4462 (`as Error` casts) — this casts to `ApiError`.
- **Suggested Fix**: Replace the inline check with a call to the existing `isApiError(error)` guard.

---

### D5-02: `types/ws/streaming.ts` uses a relative import instead of the mandated `@/` alias
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/types/ws/streaming.ts:8`
- **Status**: NEW
- **Description**: CLAUDE.md mandates `@/` absolute imports only. Every production file under `src/` complies except this one, which imports `EnhancementPreset` via `'../domain'`. #4466 covers the same convention violation but is explicitly scoped to 15 *test* files; this is the only production-source instance.
- **Evidence**:
  ```ts
  import type { EnhancementPreset } from '../domain';
  import type { WebSocketMessage } from './base';
  ```
- **Impact**: Cosmetic — TypeScript resolves either form. But it is the last production exception to an otherwise fully-enforced convention and will get copy-pasted into new WS type files.
- **Siblings**: None in production; #4466 covers the test files.
- **Suggested Fix**: `import type { EnhancementPreset } from '@/types/domain';`

---

### Y8-02: No `<h1>` (or any level-1 heading) exists anywhere in the running app
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/core/AppTopBar.styles.ts` (`TitleBox`, used via `auralis-web/frontend/src/components/core/AppTopBarLeftSection.tsx:29`), `auralis-web/frontend/src/ComfortableApp.tsx:284`
- **Status**: NEW
- **Description**: The prominent page title in the top bar (e.g. "Your Music") renders through `TitleBox`, a plain `styled(Box)` — a `<div>`, never a heading. Repo-wide grep finds no `<h1>`/`variant="h1"` in normal app flow; the only `<h1>` usages are in `components/core/ErrorBoundary.tsx` and the `index.tsx` fatal-init fallback, both exceptional states. The highest heading level used for real content is `<h2>`.
- **Evidence**:
  ```ts
  export const TitleBox = styled(Box)({ fontSize: tokens.typography.fontSize.xl, ... });
  ```
  ```tsx
  {!showMobileMenu && <TitleBox>{title}</TitleBox>}
  ```
- **Impact**: Screen-reader users navigating by heading level (the "H" shortcut in NVDA/JAWS/VoiceOver) never land on a document-level heading and jump straight to `h2`; the app's own title text is never exposed as a heading at all. Not a blocker — `banner` and `main` landmarks are correctly present.
- **Siblings**: None — a single app-wide gap.
- **Suggested Fix**: Render `TitleBox` as `component="h1"` keeping existing visual styles, and nest the remaining `h2`s under it.

---

### Y8-03: Switching library views is not announced to screen readers
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx:249-296`
- **Status**: NEW
- **Description**: `handleSidebarNavigation` swaps `currentView`, re-rendering `<AppMainContent>` with an entirely different view, but there is no `aria-live` region, focus move, or other announcement anywhere in the app shell (`ComfortableApp.tsx`, `AppContainer.tsx`, `AppMainContent.tsx`, `AppTopBar.tsx` — none contain `aria-live`). This is the SPA equivalent of a route change with no page-change announcement.
- **Evidence**: `grep aria-live` over `ComfortableApp.tsx` and `components/core/*.tsx` returns zero matches; `handleSidebarNavigation` at `:249-251` calls `setCurrentView(view)` with no follow-up.
- **Impact**: A screen-reader user activating a sidebar nav item gets no confirmation that main content changed and must re-explore the main landmark. Distinct from #4474 (playback-state announcement) — this is section navigation.
- **Siblings**: None.
- **Suggested Fix**: Add a visually-hidden `aria-live="polite"` status region announcing the new view name on `currentView` change, following the existing `GlobalSearch.tsx` (`role="status" aria-live="polite"`) pattern.

---

### TC9-01: `deinterleaveToOutput` has no direct tests; its multichannel and stereo-shortfall branches are unexercised
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/services/audio/deinterleaveToOutput.ts:1-65`
- **Status**: NEW
- **Description**: This is the pure function that copies decoded PCM into the Web Audio output buffer on every `onaudioprocess`/worklet callback — the last step before audio reaches the speakers. Its own docstring says it was extracted "so it is trivially unit-testable without mocking an AudioContext," yet no dedicated test file exists. Coverage is entirely indirect via `services/audio/__tests__/BufferScheduler.test.ts`, which reaches only two of three branches. Untested: the stereo silence-padding loop (lines 41-44, buffer-underrun protection) and the entire 3+-channel branch (lines 47-56).
- **Evidence**:
  ```ts
  // lines 41-44 — silence padding on under-supply, untested
  for (let i = framesToProcess; i < framesNeeded; i++) { left[i] = 0; right[i] = 0; }
  // lines 47-56 — 3+ channel branch, untested (no test constructs a 3+ channel output)
  ```
- **Impact**: Both untested branches read correctly on inspection, so this is a coverage gap rather than a live defect — but it sits on the real-time audio output path, where a regression manifests as audible glitches rather than a failed assertion. The under-supply branch guards exactly the buffer-underrun edge case that caused #4331.
- **Siblings**: None — `PCMStreamBuffer.test.ts` and `PlaybackPositionTracker.test.ts` (the other two pure modules from the same #4301 refactor) are both thoroughly tested.
- **Suggested Fix**: Add `services/audio/__tests__/deinterleaveToOutput.test.ts` covering the stereo shortfall (assert the tail is exactly zero-filled) and a 3-channel case. No AudioContext mocking needed.

---

## Relationships

**Cluster 1 — `useQueueMutations` is an untested contract boundary (A6-01, A6-02, T4-01).**
Both 422 bugs live in the same file, and both survived two prior audits for the same structural reason: the hook's tests mock `useRestAPI` wholesale, so they assert that a mocked promise resolves, never that the URL and body match the backend. T4-01 is the type-level statement of the same gap — `useRestAPI` performs no runtime validation, so nothing anywhere in this stack can detect endpoint drift. Fixing T4-01 (or adding literal URL/body assertions) is what prevents a third instance.

**Cluster 2 — closed fixes that stopped one call site short (P7-01, P7-02, A6-01).**
#4445 disposed the engine at two of three drop sites; #4447 sized artwork at four of five; #4536 added keyboard reorder that routes into a broken endpoint. The shared root cause is fixing at the *call site* rather than the *choke point*: P7-01's correct fix is inside `cleanupStreaming()` (which all paths funnel through), not at each caller. Any publish of these should note the sibling-sweep requirement explicitly.

**Cluster 3 — the theme migration's untracked remainder (D5-01, C1-01).**
D5-01's 103 files include the entire dead `features/discovery/` tree from C1-01, so deleting that tree mechanically shrinks the migration surface. Fixing the design-system primitives (`Button`, `Input`, `IconButton`, `Badge`, `Slider`) first propagates to every consumer and is the highest-leverage slice.

**Cluster 4 — dead code as a recurring shape (C1-01, R2-01, R2-03, T4-02, T4-03).**
Five findings across four dimensions are all "declared, exported, documented, never used." Three prior audits each found a fresh instance. The common factor is that nothing in CI detects unreferenced exports — a `knip`/`ts-prune` gate would collapse this entire category.

**Cluster 5 — stale-response races in the library fetch layer (H3-01, H3-02).**
Both are the same defect shape (an async fetch whose late resolution writes into state belonging to a newer request) in two parallel pagination implementations. The two hooks are themselves near-duplicates — consolidating them would fix both races at once and is consistent with the project's no-variants rule.

---

## Prioritized Fix Order

1. **A6-01** — queue reorder wrong endpoint. One-line fix; restores a completely broken core feature and retroactively makes #4536's accessibility fix functional. Highest value-to-effort ratio in this report.
2. **A6-02** — shuffle wrong parameter location. One-line fix, same file, same session. Also correct the misleading `useRestAPI` docblock so the pattern stops propagating.
3. **P7-01** — GainNode leak on skip. One line inside `cleanupStreaming()`; closes the leak for `stopPlayback`, `handleStreamError`, and all future callers at once.
4. **T4-01 (partial) / regression tests for 1-2** — add literal URL+body assertions to `useQueueMutations` tests before or alongside the fixes above, so this class of drift cannot recur silently. This is the structural fix for Cluster 1.
5. **D5-01** — theme migration remainder. Large but mechanical; sequence as (a) delete the `features/discovery/` dead tree per C1-01, (b) convert the design-system primitives, (c) convert `TrackRow`/`TrackTableRowItem`, (d) the rest. File a tracking issue first — it currently exists only in a doc.
6. **H3-01, H3-02** — library fetch races. Fix together by consolidating the two pagination hooks rather than patching each.
7. **C1-02** — settings ErrorBoundary. Small, follows an established in-repo pattern, and protects active playback.
8. **P7-02, Y8-01** — one-line artwork size hint; one-attribute listbox role.
9. **T4-02, C1-01, R2-01, R2-03** — dead-code removals. Batch into one cleanup pass and consider adding a `knip`/`ts-prune` CI gate to stop the category from regrowing.
10. **Remaining LOW** (C1-03, R2-02, H3-03, T4-03, T4-04, D5-02, Y8-02, Y8-03, TC9-01) — opportunistic.

---

## Verified, Not Reported

Recorded so future audits do not re-investigate:

- **#4534, #4535** (theme) — both fixes intact and now guarded by `theme/__tests__/cssCustomPropertyProducers.test.ts`. A repo-wide sweep found zero remaining phantom `var(--…)` custom properties.
- **#4536, #4537, #4448, #4449, #4450, #4451** (accessibility) — all re-verified fixed. Note that #4536's *keyboard handler* is intact; it is the endpoint underneath it that is broken (A6-01).
- **#4446** (icon barrel imports), **#4471** (virtualized cache lists) — fixes hold.
- **#4522, #4436, #4406, #4438, #4583, #4609** (hooks) — all re-verified fixed in current source.
- **Effect-cleanup sibling sweep** — every `useEffect` under `src/hooks/` that opens a subscription, timer, or listener has a matching cleanup. Three effects lack one (`useAppLayout.ts`, `useLibraryWithStats.ts`, `useLibraryQuery.ts`); each was individually confirmed to correctly need none.
- **Contrast tokens** — `text.secondary` (0.68α), `text.metadata`/`text.tertiary` (0.60α), and `text.muted` (0.50α) were manually computed against `bg.level0`–`bg.level4`; all pass 4.5:1 for normal text (worst case ≈4.76:1). Only the already-filed `text.disabled` (#4635) fails.
- **WebSocket type contracts** — `types/ws/*` message shapes were cross-referenced against the real backend emitters in `ws_handlers/` and `core/stream_*.py`; binary/text frame discrimination in `websocketConnectionCore.ts` is correct.
- **Global auto-mock discipline** — all six `contexts/__tests__/WebSocketContext.*.test.tsx` files correctly `vi.unmock()` before exercising real behavior. No test asserts against the mock while claiming to test the implementation.
- **Dead code deliberately not reported as bugs** — `usePlayNormal()` and `useQueueHistory()` each contain plausible-looking defects but have zero live call sites; reporting them would misrepresent runtime impact. `design-system/primitives/Toggle.tsx` sets `outline: 'none'` inline with no replacement but is likewise unreachable.
- **H3-04, effect-cleanup sibling sweep** (the mandatory sweep result, not a defect) — grepping every `useEffect` under `src/hooks/` found exactly three files with an effect lacking a cleanup function: `hooks/app/useAppLayout.ts:61-70,72-80` (only sets state from media-query booleans; opens nothing), `hooks/library/useLibraryWithStats.ts:65-70` (only triggers `fetchTracks`/`refetchStats`; the callees own their own abort lifecycles), and `hooks/library/useLibraryQuery.ts:425-435` (unmount-abort lives in `useRestAPI`, supersession in `requestIdRef` post-#4609). All three confirmed correct by design. Worth a one-line "no cleanup needed" comment in the first two so future auditors need not re-derive it.

---

*Generated by `/audit-frontend` on 2026-07-29. Next step: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-07-29.md`*
