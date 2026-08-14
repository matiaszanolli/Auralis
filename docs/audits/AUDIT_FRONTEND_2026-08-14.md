# Frontend Audit — 2026-08-14

**Scope**: `auralis-web/frontend/src/` — components, Redux store, hooks, TypeScript types,
design system, API client, performance, accessibility, test coverage.
**Method**: 9 dimension agents, deep depth, fresh read of the working tree at `master`
(`c1582f2f`). Every finding deduplicated against 1,500 GitHub issues (open **and** closed),
`auralis-web/frontend/test-baseline.json`, and the prior frontend reports.
**Out of scope**: Python backend, audio engine, Rust DSP, database.

> **Read this first.** The previous frontend audit — `docs/audits/AUDIT_FRONTEND_2026-08-13.md`,
> 28 findings, dated **yesterday** — was never published as GitHub issues (no `.claude/issues/`
> snapshot references it). Every dimension agent in this run was given that report as a mandatory
> dedup input, so this report is **additive to it, not a replacement**. Ten of its findings were
> re-verified as still present and are listed here by their original IDs without re-description;
> the 21 findings below marked NEW are ones it did not contain. **Publishing yesterday's report
> is still outstanding work** — see *Publishing Status*.

---

## Executive Summary

| Severity | New this run | Re-verified from 2026-08-13 | Total live |
|---|---|---|---|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 0 | 2 |
| MEDIUM | 8 | 5 | 13 |
| LOW | 11 | 5 | 16 |
| **Total** | **21** | **10** | **31** |

**Two HIGH findings, both independently re-verified by the orchestrator against HEAD before
inclusion.** Neither was known to any prior report.

1. **FE-C6-03** — both "toggle favorite" controls in the app only ever issue `POST`. The backend
   has no toggle semantic: `POST` sets `favorite=True`, `DELETE` sets `favorite=False`. Un-favoriting
   therefore never reaches the server while the UI reports success. This is the only finding in the
   report that silently diverges persisted user data from what the user was shown.
2. **FE-C9-01** — 14 files under `src/tests/integration/` and `src/tests/api-integration/` import
   **zero production code**. Each renders a throwaway component defined inside the test file, while
   its docblock and the directory README claim integration coverage of search, filter, sort,
   metadata, artwork, accessibility, pagination, caching, bundle splitting, and memory cleanup.

### Key themes

**1. The dominant theme is unchanged from yesterday, and this run sharpens it: a correct fix exists
and never reached its siblings.** 9 of the 21 new findings are of the form "this exact bug was found,
fixed, and closed elsewhere in the codebase; the structurally identical site was never swept."
Concretely: FE-C6-02 is #4847 fixed in `useTrackFingerprint.ts` but not `useAlbumFingerprint.ts`;
FE-C3-01 is #4436 fixed in `useWebSocketConnection.ts` but not `useQueueHistory.ts`; FE-C8-03 is
#4537 fixed in `AlbumsTab.tsx` but not `AlbumArt.tsx`; FE-C6-01 and FE-C6-05 are sites outside the
enumerations of yesterday's own FE-A-2/FE-A-4; FE-C9-01 is the `streaming-mse.test.tsx` fix (#3935)
never generalized to its 14 siblings. This is the same organizational pattern the 2026-08-13 engine
audit named as the root cause behind all three of its HIGH findings. **A sibling sweep at fix time
would have prevented roughly half of this report.**

**2. Tests that certify the thing they don't test.** FE-C9-01 through FE-C9-05 are five independent
instances of a suite asserting nothing while reporting green — fabricated fixture components (C9-01),
assertions that are true by construction (`activeElement` is always in the document, C9-02;
`mock.calls.length >= 0`, C9-03/C9-04), and assertions nested inside an `if` with no `else` so a DOM
regression skips the test body entirely (C9-05). Combined with yesterday's FE-Q-1..4 and FE-D-1, the
frontend's *stated* coverage is materially ahead of its real coverage, and the gap is invisible to
anyone reading test names or counts.

**3. Dead code that occupies the canonical name.** Five design-system primitives have zero consumers
(FE-C5-01), including the more accessible of two competing progress bars; three `ErrorBoundary`
implementations exist with incompatible prop contracts and only one is ever mounted (FE-C1-02); three
`Playlist` type declarations disagree and the two that look canonical are the dead, incorrect ones
(FE-C4-02); a cluster of memoized Redux selectors is reachable only through the already-dead
`performance/` barrel (FE-C2-02). None of these break anything today. All of them are what a
contributor finds first.

### Most impactful

Fix **FE-C6-03** first — it is the only user-data-correctness bug in the report, the fix is small
(branch on current state and call `del()`, mirroring `handleBulkRemove` which already does it
correctly in the same file), and no test currently guards it. Fix **FE-C9-01** next, not because it
breaks anything, but because until it is resolved the suite's green status cannot be used as evidence
about any of the ten feature areas those files claim.

---

## HIGH

### FE-C6-03: Both "toggle favorite" entry points always POST — the DELETE half is never issued
- **Severity**: HIGH
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:91-119`;
  `auralis-web/frontend/src/components/library/useBatchOperations.ts:126-142`;
  backend contract `auralis-web/backend/routers/tracks.py:134-160`
- **Status**: NEW
- **Description**: The backend exposes favorite state as two non-toggling endpoints —
  `POST /api/library/tracks/{id}/favorite` unconditionally sets `favorite=True`, `DELETE` on the same
  path unconditionally sets it `False`. Each handler calls `repos.tracks.set_favorite(track_id, True|False)`
  directly with no read-current-state-first logic; there is no toggle semantic on the wire. Both of
  the app's "toggle favorite" controls only ever call the POST half:
  - `useAlbumDetails.ts`'s `toggleFavorite` (the heart button in the Album Detail header, wired
    `AlbumDetailView.tsx:201` → `AlbumHeaderActions.tsx:94`) always issues `method: 'POST'`, then flips
    a **local** boolean without reading the response's `favorite` field. That local `isFavorite` is
    `useState(false)` and is never initialized from the track's real favorite value on load.
  - `useBatchOperations.ts`'s `handleBulkToggleFavorite` (the "Toggle Favorite" button in
    `BatchActionsToolbar`, rendered in every context) issues `post(ENDPOINTS.TRACK_FAVORITE(trackId))`
    for every selected track regardless of current state, then reports `"Toggled favorite for N tracks"`.

  A correctly-implemented sibling sits in the same file: `handleBulkRemove` (`useBatchOperations.ts:104-124`,
  wired only in the `favorites` context) correctly issues `del(ENDPOINTS.TRACK_FAVORITE(trackId))`.
- **Evidence**: Verified independently by the orchestrator at HEAD. `useAlbumDetails.ts:101-112` is
  `fetch(..., { method: 'POST' })` followed by `setIsFavorite(!isFavorite)`; `useAlbumDetails.ts:33` is
  `useState(false)`. `useBatchOperations.ts:126-130` uses `post(...)` where its sibling at `:113` uses
  `del(...)`. `grep -rn "TRACK_FAVORITE\|/favorite"` across non-test frontend source returns only these
  two implementations plus the correct `handleBulkRemove`.
  **Disproof attempted**: searched for a third, correct single-track toggle by grepping every
  `onToggleFavorite=` prop assignment app-wide. `SelectableTrackRow`/`TrackRow` accept an
  `onToggleFavorite` prop, but their only render site (`TrackListViewContent.tsx:121-131`) never supplies
  one — that path is inert, so it neither rescues nor duplicates this finding. Both backend handlers were
  read in full to confirm neither reads prior state.
- **Impact**: A user who favorites a track from Album Detail or a bulk selection, then clicks the same
  control again to un-favorite, sees the UI flip to "not favorited" while the backend keeps `favorite=True`
  permanently. The track keeps appearing in the Favorites view with no affordance explaining why. The only
  working way to remove a favorite is the separate "Remove from Favorites" bulk action, reachable only from
  inside the Favorites view.
- **Suggested Fix**: Branch on current favorite state in both handlers and call `DELETE` when currently
  favorited, mirroring `handleBulkRemove`. Read the real `favorite` field back from each response instead
  of flipping local state blindly, and initialize `useAlbumDetails`'s `isFavorite` from the fetched track.
  For the bulk path, thread each selected track's current state through, or split into
  `handleBulkFavorite`/`handleBulkUnfavorite` the way `handleBulkRemove` already models.

### FE-C9-01: 14 "integration" test files import zero production code
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/library-management/` — `accessibility.test.tsx`,
  `artwork.test.tsx`, `filter.test.tsx`, `metadata.test.tsx`, `search.test.tsx`, `sort.test.tsx`;
  `src/tests/integration/error-handling/error-handling.test.tsx`;
  `src/tests/integration/performance/` — `bundle-size.test.tsx`, `cache-efficiency.test.tsx`,
  `memory-management.test.tsx`, `pagination.test.tsx`, `virtual-scrolling.test.tsx`,
  `performance-large-libraries.test.tsx`; `src/tests/api-integration/library-api.test.ts`
- **Status**: NEW (distinct from yesterday's FE-Q-1, which covers `src/components/__tests__/Integration.test.tsx`
  and `redux-flow.test.tsx` — a different directory and a different failure shape: dead `vi.mock()` paths
  vs. never importing production code at all)
- **Description**: Each file's only non-test-infrastructure imports are `vitest`, `@testing-library/react`,
  `@/test/test-utils`, `msw`, and `react`. None imports anything from `@/components`, `@/hooks`, `@/services`,
  `@/store`, or `@/contexts`. Each instead defines a throwaway component inline — `SearchableLibrary`,
  `CachedLibrary`, `VirtualList`, `LazyLoadTest`, `ComponentWithListeners` — with hand-rolled logic that
  approximates but is architecturally unrelated to the real feature. `api-integration/library-api.test.ts`
  does not even render: it calls bare `fetch()` against MSW mocks and never touches `libraryService`,
  `useLibraryPagination`, or `useInfiniteAlbums`.

  Three siblings in the same tree prove the pattern is avoidable: `library-management.test.tsx` renders the
  real `CozyLibraryView`, `playlist-management.test.tsx` imports the real `PlaylistList` and `playlistService`,
  and `websocket-realtime.test.tsx` `vi.unmock()`s and exercises the real `WebSocketContext`. A fourth,
  `streaming-audio/streaming-mse.test.tsx`, had exactly this defect, was caught (#3935), and was fixed with
  `describe.skip` plus real coverage in `AudioPlaybackEngine.test.ts` — **that fix was applied to one file
  and never swept across the directory.**
- **Evidence**: Verified independently by the orchestrator: `search.test.tsx`, `virtual-scrolling.test.tsx`,
  `error-handling.test.tsx`, and `library-api.test.ts` were each checked and import only vitest /
  testing-library / msw / React, with inline fixture components (`SearchableLibrary` at `search.test.tsx:22`,
  `TestAPIComponent`/`TestConcurrentComponent`/`TestRetryComponent` at `error-handling.test.tsx:26-99`).
  **Production-change proof**: delete `useLibraryPagination`/`useInfiniteAlbums` outright, or remove
  virtualization from `TracksTab`, and every test in this list still passes. `virtual-scrolling.test.tsx`'s
  "memory efficient with large lists" test asserts a locally-defined `VirtualList` renders ~10 of 10,000
  nodes — which says nothing about `TracksTab`, and per FE-P-2 (yesterday, still open) `TracksTab` currently
  does **not** virtualize at all.
  **Disproof attempted**: grepped the whole tree for imports of `@/components`, `@/hooks`, `@/store`,
  `@/contexts`, `@/services`, and any relative import — zero relative imports exist anywhere in the tree, and
  only the three named siblings import real code. `streaming-mse.test.tsx` was read in full to confirm it is
  already skipped rather than a live instance.
- **Impact**: A regression or outright deletion of library search, filter, sort, metadata editing, artwork
  management, accessibility, API error handling, pagination, caching, bundle splitting, or memory-leak
  cleanup produces zero test failures. The README and each docblock ("Part of Week 4 frontend testing
  roadmap (200-test suite)") actively mislead a coverage audit. This is worse than a missing test: it exists,
  passes, and consumes CI time while asserting nothing.
- **Suggested Fix**: Per file, either delete it and rely on real component/hook tests (precedent:
  `AudioPlaybackEngine.test.ts` replaced the fake MSE suite), or rewrite it to render the production
  component it claims to cover, following `library-management.test.tsx`. At minimum, correct the README and
  docblocks so they stop claiming coverage that does not exist.

---

## MEDIUM

### FE-C1-01: Every virtualized library grid/list paints its full unvirtualized fallback before swapping
- **Severity**: MEDIUM · **Dimension**: Component Quality · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx:193-244`,
  `Items/albums/EraSection.tsx:67-115`, `Views/TrackGridView.tsx:64-84`,
  `Items/artists/ArtistListContent.tsx:97-142`
- All four gate `canVirtualize` on a `scrollReady` state set inside a plain `useEffect` rather than
  `useLayoutEffect` — unlike the sibling `containerWidth` measurement in the same files, which correctly
  uses `useLayoutEffect` (`useGridVirtualizer.ts:62-66`). Passive effects run *after* paint, so every mount
  renders and paints the fallback branch (which `.map()`s every item with no windowing), then swaps to a
  structurally unrelated virtualized tree, unmounting and remounting the entire subtree.
- The `// jsdom / unmeasurable layout` comments frame this as test-only, but nothing gates it to tests —
  `document.getElementById('app-main-content-scroll')` resolves on the same timing in real Electron runs.
- **Impact**: A visible flash on every navigation into Albums / Tracks-grid / Artists, transiently defeating
  the DOM-node bound virtualization exists to guarantee. `EraSection` is worst: one era-grouped view mounts
  N instances that each replay it.
- **Disproof attempted**: checked for a `Suspense` boundary that would defer the first commit (none covers
  this transition) and for a cached ref surviving remount (all four use fresh component-local state).
  `TrackListViewContent.tsx` was checked and does **not** have the defect — it has no fallback branch at all.
- **Fix**: switch the four `scrollReady` initializations to `useLayoutEffect`.

### FE-C6-01: `usePlayTrack`'s queue-set POST discards the backend's error `detail`
- **Severity**: MEDIUM · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:48-61`
- Same defect class as yesterday's FE-A-2, but on a file outside its five-site enumeration — and this is the
  app's documented "single source of truth for 'play this track now'". It throws a hardcoded
  `` `Failed to set queue: ${status} ${statusText}` `` instead of routing through `httpErrorFromResponse()`.
- **Disproof attempted**: confirmed the path is live (not superseded by `useEnhancedPlayCommand`) and that
  `POST /api/player/queue` genuinely raises `HTTPException(detail=...)` with actionable text.
- **Fix**: `throw await httpErrorFromResponse(queueResponse)`.

### FE-C6-02: `useAlbumFingerprint` swallows every error into `null` — #4847 fixed only in its sibling
- **Severity**: MEDIUM · **Dimension**: API Client · **Status**: NEW (sibling gap on closed #4847)
- **Location**: `auralis-web/frontend/src/hooks/fingerprint/useAlbumFingerprint.ts:29-47`;
  correct sibling `useTrackFingerprint.ts:36-48`
- `useTrackFingerprint` deliberately lets non-404 failures reject, with a comment citing #4847 ("a 404 and
  'the endpoint is broken' used to be indistinguishable"). `useAlbumFingerprint` wraps identical logic in
  `try { ... } catch { return null; }`, so its own `throw` is caught two lines later and converted back to
  `null`. The `queryFn` never rejects; `query.error` is permanently `undefined`.
- **Impact**: A 5xx or network failure on `/api/albums/{id}/fingerprint` is indistinguishable from "no
  fingerprint yet" — every album cover silently falls back to a hash gradient with no diagnostic signal.
  The batch variant inherits it: `Promise.allSettled`'s `'rejected'` branch is dead code for this call.
- **Fix**: mirror `useTrackFingerprint` — return `null` only for 404, let the rest propagate.

### FE-C6-04: `createCrudService` guards only `list`/`get`; every write response is unvalidated by construction
- **Severity**: MEDIUM · **Dimension**: API Client · **Status**: NEW
- **Location**: `auralis-web/frontend/src/utils/serviceFactory.ts:60-83` (`guards` type), `:126-139`, `:141-154`, `:163-193`
- #4607's runtime-guard mechanism reached `createCrudService` via a `guards` config whose type declares only
  `list?`/`get?`. There is no `create`/`update`/`delete`/`custom` key a service author *could* populate, and
  each of those methods calls `requestOptions(undefined, options)` unconditionally. This caps guard coverage
  at read paths for `playlistService`, `queueService`, `settingsService`, and `artworkService`.
- Not hypothetical: `settingsService.updateSettings` returns `result.settings` straight into the Settings form
  state with no shape check, while its sibling `getSettings()` guards the same shape via `isUserSettingsShape`.
- **Disproof attempted**: checked whether write responses are low-risk acks — they are not; these payloads
  populate rendered UI state. Checked whether a caller could pass `validate` as a workaround —
  `CrudRequestOptions` is deliberately narrowed to `Pick<RequestOptions, 'signal'>` to prevent exactly that.
- **Fix**: extend `CrudEndpoints.guards` with `create`/`update`/`custom` keys and thread them through.

### FE-C8-01: Global search "clear" button is a bare `<svg>` — unreachable by keyboard, invisible to AT
- **Severity**: MEDIUM · **Dimension**: Accessibility · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/library/Search/SearchInput.tsx:54-64`
- The clear affordance is an MUI `CloseIcon` (renders a plain `<svg>`) with `onClick` and `cursor: 'pointer'`,
  no `role="button"`, no `tabIndex`, no key handler. MUI's `SvgIcon` also sets `aria-hidden={titleAccess ? undefined : true}`,
  and no `titleAccess` is passed — so it is absent from the accessibility tree entirely.
- **Disproof attempted**: checked `GlobalSearch.tsx` for an Escape-to-clear alternative (none). Checked the
  near-duplicate `AppTopBarSearchInput.tsx:68-81`, which implements the same affordance correctly as an
  `IconButton` with `aria-label="Clear search"` — confirming an isolated inconsistency, not a project-wide pattern.
- **Impact**: keyboard-only and screen-reader users must delete the query character by character.
- **Fix**: use an `IconButton` with `aria-label="Clear search"`, matching `AppTopBarSearchInput.tsx`.

### FE-C9-02: `AlbumDetailView.test.tsx` keyboard-navigation test passes on every code path
- **Severity**: MEDIUM · **Dimension**: Test Coverage · **Status**: NEW (not in `test-baseline.json`)
- **Location**: `auralis-web/frontend/src/components/library/__tests__/AlbumDetailView.test.tsx:760-789`
- After pressing Enter the test asserts `expect(document.activeElement).toBeInTheDocument()` — always true,
  since `activeElement` falls back to `<body>`. The `else` branch re-asserts a fact already established above.
- **Production-change proof**: remove Enter-activation from the play button entirely; the test still passes.
- **Fix**: assert a real effect (`expect(mockPlayTrack).toHaveBeenCalled()`) and use
  `getByRole('button', { name: /play album/i })` so a missing button fails loudly.

### FE-C9-03: `AlbumArt.test.tsx`'s only click test cannot detect a broken handler
- **Severity**: MEDIUM · **Dimension**: Test Coverage · **Status**: NEW (not in `test-baseline.json`)
- **Location**: `auralis-web/frontend/src/components/album/AlbumArt.test.tsx:114-131`
- Asserts `expect(handleClick.mock.calls.length).toBeGreaterThanOrEqual(0)` — true by construction for any
  `vi.fn()`, called or not, inside an `if (element)` guard.
- **Production-change proof**: delete the `onClick={onClick}` wiring from `AlbumArt.tsx`; the test still passes.
- **Fix**: `expect(handleClick).toHaveBeenCalledTimes(1)`, unconditionally.

### FE-C9-05: Four click-handler tests skip their only assertion if the target stops being a `<button>`
- **Severity**: MEDIUM · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `auralis-web/frontend/src/components/__tests__/Sidebar.test.tsx:40-48,67-73,76-83`;
  `src/components/__tests__/RadialPresetSelector.test.tsx:61-73`
- Each locates the target via `getByText(...).closest('button')` and fires the click plus asserts the callback
  **inside** `if (button) { ... }` with no `else` and no assertion outside. `getByText` throws if the label
  vanishes, so the blind spot is precisely "label still present, wrapper is no longer a `<button>`" — exactly
  what an MUI `ListItemButton`/`Box` refactor produces. Vitest reports a pass with zero assertions run.
- **Impact**: sidebar navigation, collapse toggle, and settings-open are core chrome; a DOM-structure
  regression in any of them ships green.
- **Fix**: `getByRole('button', { name: ... })` and move the `expect` calls outside the conditional.

### Re-verified from 2026-08-13 (still present, not re-described)
- **FE-D-1** (MEDIUM) — `src/index.css` never loaded; a dead 451-line competing token system that 2 vitest
  suites and 4 open issues (#3927, #4171, #3636, #4172) treat as authoritative. Re-checked:
  `grep -n "index.css"` against `index.html` and `src/index.tsx` still returns nothing; no commit since
  `be0f3619` (2025-11-22) restored the import.
- **FE-D-3** (MEDIUM) — MUI `sx` numeric spacing shorthand is a second, unmapped spacing scale.
  Newly confirmed this run: `design-system/__tests__/spacingTokens.test.ts`'s #4663 guard only pattern-matches
  literal `(padding|margin|gap): '...'` strings and structurally cannot catch the `sx` numeric form.
- **FE-P-1** (MEDIUM, also a regression of closed #3607) — `ArtistListItem` unmemoized; right-clicking any
  artist re-renders every row in the virtualized window.
- **FE-P-2** (MEDIUM) — Artist-detail "Tracks" tab renders the full track array unvirtualized.
- **FE-P-3** (MEDIUM) — `QueueSearchPanel` renders filtered results unvirtualized and unmemoized.

---

## LOW

| ID | Title | Location | Status |
|---|---|---|---|
| **FE-C1-02** | Three `ErrorBoundary` implementations with incompatible `fallback` contracts; only `components/core/` is ever mounted, and the dead one is the one exported from the design-system barrel | `components/core/ErrorBoundary.tsx`, `design-system/primitives/ErrorBoundary.tsx`, `performance/lazyLoader.tsx:58-86` | NEW (the `performance/` copy overlaps open #4696; the design-system copy does not) |
| **FE-C2-02** | A cluster of memoized cross-domain selectors has zero production consumers, reachable only via the dead `performance/` barrel — so the #4696 cleanup would orphan it unless swept in the same pass | `store/selectors/{combined,player,queue,cache,connection}.ts`, `store/slices/connectionSlice.ts:220-236` | NEW (disjoint from #5016 and closed #4395) |
| **FE-C3-01** | `useQueueHistory`'s `isMountedRef` is never reset to `true` on remount — the exact #4436 bug class, fixed in `useWebSocketConnection.ts` and in siblings `usePlayTrack.ts`/`useLibraryScan.ts`, unfixed here. Dormant: zero production call sites | `hooks/player/useQueueHistory.ts:167-171` | NEW |
| **FE-C3-02** | `useIsFingerprintCached`/`useCachedFingerprint` have no out-of-order guard on rapid `trackId` change, unlike every other keyed-async hook (`useLibraryQuery`, `useSimilarTracks`, `useArtworkPalette`). Dormant: no production consumer | `hooks/fingerprint/useFingerprintCache.ts:213-246` | NEW |
| **FE-C4-01** | `TrackApiResponse`/`AlbumApiResponse`/`ArtistApiResponse` omit 22 fields the backend genuinely serializes (traced through each `to_dict()`), including the DR/LUFS/mastering-quality fields most relevant to this app's domain | `api/transformers/types.ts:15-24,38-51,65-114` | NEW |
| **FE-C4-02** | Three divergent `Playlist` declarations; the two that look canonical are dead **and** missing 6 real fields including `auto_master_enabled`/`mastering_profile`, while the live hand-rolled copy in `playlistService.ts` is correct | `types/api.ts:196-204`, `types/domain.ts:107-118`, `api/transformers/playlistTransformer.ts`, `services/playlistService.ts:17-31` | NEW |
| **FE-C5-01** | Five of 22 design-system primitives have zero consumers; sharpest case is two competing progress bars where the fully-ARIA'd `ProgressBar.tsx` is the dead one and `LinearProgress.tsx` is live, plus a third raw-MUI bypass | `design-system/primitives/{Input,Badge,Checkbox,ProgressBar,Text}.tsx`; bypass at `components/library/AlbumCharacterPane/PanePlaceholders.tsx:2` | NEW |
| **FE-C6-05** | Three more hardcoded relative URLs outside FE-A-4's ten-site enumeration | `hooks/fingerprint/useTrackFingerprint.ts:37`, `useAlbumFingerprint.ts:31`, `useSimilarTracks.ts:176` | NEW |
| **FE-C8-02** | `design-system/primitives/Modal.tsx`'s close `IconButton` has no accessible name by any mechanism — no `aria-label`, not even a `tooltip`. Dead code today, but it is the canonical Modal any future dialog would copy | `design-system/primitives/Modal.tsx:119-125` | NEW |
| **FE-C8-03** | `AlbumArt`'s `onClick` drives pointer/hover styling but no `role`/`tabIndex`/`onKeyDown` — the shape #4537 was filed and fixed for elsewhere. Latent: both production callers omit `onClick` | `components/album/AlbumArt.tsx:25-44,83-107` | NEW |
| **FE-C9-04** | `AlbumDetailView.test.tsx` genre and track-number tests assert `length >= 0`; sibling tests in the same `describe` correctly use `toBeGreaterThan(0)`, so this is a localized slip | `components/library/__tests__/AlbumDetailView.test.tsx:159-167,262-267` | NEW (not in `test-baseline.json`) |

### Re-verified from 2026-08-13 (still present, not re-described)
- **FE-R-1** — `handleChunk`'s decode-error path omits `trackId`, bypassing the #4434 stale-stream guard, while
  its three sibling dispatches in the same file all pass it (`hooks/enhancement/useAudioStreamingCore.ts:365-369`).
  Two further sites confirmed sharing the shape: `useEnhancedPlayCommand.ts` and `useEnhancedStreamStart.ts:218`.
  *Rated MEDIUM yesterday; carried here at its original severity.*
- **FE-R-2** — `useAppErrors`/`useConnectionHealth` return unmemoized object literals while the four sibling
  hooks in the same file are all `useMemo`-wrapped (`hooks/shared/useReduxState.ts:410-445`). Zero production
  call sites, so latent only.
- **FE-H-2** — `useMasteringRecommendation`'s per-track cache has no eviction, unlike `paletteCache` and
  `similarityCache` which were both given bounds.
- **FE-D-2** — Raw hex literals bypass tokens in `store/middleware/loggerMiddleware.ts:63-67,215,221` and
  `components/player/ShuffleModeSelector.module.css:59,86`. An independently-constructed sweep this run
  reproduced exactly these two files and no others — four additional grep hits resolved to migration comments.
- **FE-D-4** — MUI theme breakpoints never wired to `tokens.breakpoints`; they match numerically today by
  coincidence, not by construction.

---

## Relationships

- **One root cause behind nine findings: fixes not swept to siblings.** FE-C6-02 (#4847), FE-C3-01 (#4436),
  FE-C8-03 (#4537), FE-C9-01 (#3935), FE-C6-01 and FE-C6-05 (outside yesterday's own FE-A-2/FE-A-4 lists),
  FE-C1-01 (the `useLayoutEffect` pattern applied to `containerWidth` but not `scrollReady` in the same files),
  FE-C6-04 (#4607 applied to read paths only), and FE-C8-02 (the FE-Y-3 gap reproduced in the canonical Modal)
  are all the same organizational failure. This is the identical theme the 2026-08-13 **engine** audit
  identified behind all three of its HIGH findings — it is a cross-cutting process gap, not a frontend one.
  **The cheapest structural mitigation is to make "grep for structurally identical sites" a required step of
  the fix workflow, not the audit workflow.**
- **FE-C9-03 is why FE-C8-03 has no guard.** `AlbumArt`'s only click test cannot fail, so the component's
  keyboard-affordance gap would not be caught by the suite even once a caller wires `onClick`. Fix them together.
- **FE-C9-01 ↔ FE-P-2 is a live false-confidence chain.** `virtual-scrolling.test.tsx` asserts a fabricated
  `VirtualList` windows correctly, while the real `TracksTab` it implies coverage for is not virtualized at all
  (FE-P-2, open since yesterday). The test's existence is an active reason someone would not look.
- **FE-C2-02 blocks the clean resolution of #4696.** Deleting the dead `performance/` directory as #4696
  recommends would orphan the selector cluster, since that barrel is its only importer. Resolve in one pass.
- **FE-C5-01, FE-C1-02, and FE-C4-02 are one shape.** In each, the artifact carrying the canonical name
  (design-system barrel export, `types/domain.ts`, `design-system/primitives/`) is the dead and/or incorrect
  one, and the live correct implementation sits somewhere less discoverable. Each will be found first by the
  next contributor.

---

## Prioritized Fix Order

1. **FE-C6-03** (HIGH) — the only user-data-correctness bug in the report. Small fix, correct sibling already
   in the same file, and no test guards it today.
2. **FE-C9-01** (HIGH) — until resolved, the suite's green status is not evidence about ten feature areas.
   Cheapest honest first step is correcting the README/docblocks; the real fix is per-file delete-or-rewrite.
3. **FE-C6-02** (MEDIUM) — one-line change, mirrors an already-written and already-reviewed sibling fix, and
   removes a class of silent app-wide failure.
4. **FE-C9-02, FE-C9-03, FE-C9-05, FE-C9-04** (MEDIUM×3, LOW×1) — sweep together; all are one-line assertion
   corrections, and until they are fixed the suite reports coverage it does not have.
5. **FE-C8-01** (MEDIUM) — real keyboard/AT blocker on a primary control, with a correct sibling implementation
   to copy verbatim.
6. **FE-C1-01** (MEDIUM) — one root cause copy-pasted four times; the fix is `useEffect` → `useLayoutEffect`.
7. **FE-C6-01, FE-C6-04** (MEDIUM) — API-boundary hardening. FE-C6-04 needs a small factory change first, so
   it is the larger of the two.
8. **Dead-code cluster** — FE-C1-02, FE-C2-02, FE-C4-02, FE-C5-01 (all LOW). Best done as one pass together
   with open #4696, since they interlock.
9. **Remaining LOW** — FE-C3-01, FE-C3-02, FE-C8-02, FE-C8-03, FE-C4-01, FE-C6-05: fix opportunistically when
   the surrounding code is touched. FE-C3-01/FE-C3-02/FE-C8-02/FE-C8-03 are all dormant (no production consumer)
   and should be fixed *before* their first consumer ships, not after.

---

## Publishing Status

**`docs/audits/AUDIT_FRONTEND_2026-08-13.md` (28 findings) has never been published as GitHub issues.**
Ten of its findings are re-verified above as still present; the other 18 were covered by dimensions that
found no change worth restating. Publishing this report alone would leave those 18 untracked.

Recommended order:

```
/audit-publish docs/audits/AUDIT_FRONTEND_2026-08-13.md    # 28 findings, still unpublished
/audit-publish docs/audits/AUDIT_FRONTEND_2026-08-14.md    # 21 new findings from this run
```

Publishing 08-13 first means this report's `Existing (unpublished): FE-X-N` markers resolve to real
issue numbers, and the dedup pass on 08-14 will correctly skip the ten re-verified items.

---

## Coverage and Confidence

All 9 dimensions completed; none stalled or was re-run. The two HIGH findings were independently
re-verified by the orchestrator against HEAD before inclusion — the favorite-toggle POST/DELETE contract
(both backend handlers and all three frontend call sites read directly) and the 14 fake integration files
(import lists checked directly on four of the fourteen, including one from each accused directory).

**Deliberately not executed**: the vitest suite was never run, per the standing constraint that broad runs
OOM this environment. Dimension 9 is therefore a static audit; it cross-referenced `test-baseline.json` to
confirm each reported spec is currently green rather than an already-tracked failure, but no finding here
rests on an observed test run. `pnpm run type-check:prod` was likewise not re-run — yesterday's clean
(0 errors) result was taken as the baseline.

**Lower-confidence areas**, spot-checked rather than exhaustively swept:
- Prop drilling was not swept across all ~286 component files (Dimension 1) — grep cannot separate genuine
  >2-level drilling from intentional presentational passing without reading each chain.
- Roughly 12 of ~34 WebSocket message types were re-walked against backend broadcast sites (Dimension 4);
  the remainder relied on yesterday's exhaustive pass.
- No computed-contrast sweep across every `sx`/styled colour pairing (Dimension 8) — only tokens with
  historical contrast issues plus the sites named by closed issues were recomputed. No `axe-core` run exists
  in this repo.
- Performance conclusions are structural traces (throttle constants, memo boundaries, disposal paths), not
  instrumented profiling; no dev server was started for any dimension.
- Dimension 9 confirmed FE-C9-01's import isolation by import-graph inspection, not runtime coverage
  instrumentation.

**Verified clean and worth not re-deriving**: #5006's `PlaybackSessionContext` split and #4632's `Player`
child-memoization are both intact; audio buffer disposal (`PCMStreamBuffer`/`AudioPlaybackEngine`/
`BufferScheduler`) is leak-free; the visualizer rAF loop is 30fps-throttled with correct cleanup; artwork
images use `loading="lazy"`; all four Redux slices have dedicated tests; `vi.unmock()` discipline is correct
across all 23 `WebSocketContext`-referencing specs; there are zero non-test relative `../../` imports; and
the suite contains no snapshot assertions at all.

---

*Report generated by `/audit-frontend` (9 dimensions, deep). Next step: publish 2026-08-13 first, then this
report — see § Publishing Status.*
