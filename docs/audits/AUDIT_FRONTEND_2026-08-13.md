# Frontend Audit — 2026-08-13

**Scope**: `auralis-web/frontend/src/` — components, Redux store, hooks, TypeScript
types, design system, API client, performance, accessibility, test coverage.
**Method**: 9 dimension agents, deep depth, fresh read of the working tree at
`master` (188db72a). Every finding deduplicated against 292 OPEN and 2000 CLOSED
GitHub issues, and against `auralis-web/frontend/test-baseline.json`
(126 known-failing specs of 3383).

**Out of scope**: Python backend, audio engine, Rust DSP, database.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 17 |
| LOW | 11 |
| **Total** | **28** |

**Nothing CRITICAL or HIGH was found.** This is a genuine result, not a shallow
pass: the two highest-risk surfaces — the WebSocket/PCM streaming path
(`useAudioStreamingCore.ts`, `websocketConnectionCore.ts`, `usePlayerStateSync.ts`)
and the Redux player/queue slices — were read in full and held up under
adversarial reading. Stream-epoch guards, `seq`-ordering guards, flow-control
hysteresis, StrictMode double-mount protection, AbortController coverage,
monotonic request-id generation counters, and optimistic-rollback staleness
checks are all present and correct, each annotated with the issue number that
introduced it. `pnpm run type-check:prod` is clean (0 errors), the WS message
union has a compile-time exhaustiveness assertion, and the four largest list
surfaces are virtualized.

### Key themes

**1. Good patterns exist but haven't reached every call site.** This is the
dominant theme — 12 of 28 findings are "the codebase solved this problem once,
correctly, and N sites never adopted the solution." Response-shape guards
(`responseGuards.ts`), error-detail extraction (`httpError.ts`), base-URL
resolution (`config/api.ts`), the shared focus trap (`a11y/focusManagement.ts`),
`React.memo` on list rows, and `useVirtualizer` on large lists each have a
correct canonical implementation plus a tail of unmigrated consumers. Individually
LOW-to-MEDIUM; collectively this is the frontend's main structural risk, because
each unmigrated site is invisible to anyone who checks "do we handle X?" and
finds the utility.

**2. Two closed issues whose fix is not in the code.** `FE-P-1` (#3607) and
`FE-Y-3` (#4473) are both closed-as-fixed but the fix is absent from current
source. #3607 was a two-part issue closed when only the virtualization half
landed; #4473's `aria-label` is simply not there. These are the highest-confidence,
lowest-effort items in the report and should be verified first.

**3. Dead code that self-certifies as live.** `src/index.css` (451 lines of a
complete parallel token system) has not been imported since 2025-11-22, yet two
vitest suites assert its correctness and four open issues (#3927, #4171, #3636,
#4172) describe on-screen bugs it cannot be causing. Similarly, four test files
mock module paths that no longer exist. In both cases the artifact *looks* like
coverage while providing none — worse than an acknowledged gap.

**4. Two competing scales for the same concept.** MUI's default 8px `sx` spacing
grid (87 uses across 45 files) is never mapped to `tokens.spacing`, and MUI's
breakpoints are never mapped to `tokens.breakpoints`. Values coincide by accident
at some steps and diverge at others.

### Most impactful issues

1. **FE-P-1** — `ArtistListItem` unmemoized; every context-menu open re-renders
   the whole visible artist window. Regression of #3607.
2. **FE-D-1** — `index.css` dead since 2025-11-22 while tests and four open
   issues treat it as authoritative.
3. **FE-A-1** — twelve fetch sites cast `response.json()` with no runtime guard.
4. **FE-Y-1** — Album Detail and Artist Detail views render zero `<h1>`, silently
   violating the app's own specced invariant with no test coverage.
5. **FE-Q-3** — three playlist CRUD "integration" tests pass with the feature deleted.

---

## Findings

### MEDIUM

---

### FE-P-1: `ArtistListItem` unmemoized — visible rows re-render on every context-menu open
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/ArtistListItem.tsx:25-66`, consumed from `auralis-web/frontend/src/components/library/Items/artists/ArtistListContent.tsx:130-139`
- **Status**: Regression of #3607
- **Description**: #3607 ("Artist list no virtualization + missing memo on ArtistSection — full re-render on context menu") was closed 2026-05-26 after only the virtualization half landed (#3957 — `ArtistListContent` does window rows through `useVirtualizer`). The "missing memo" half was never applied to the renamed row component. `ArtistListItem` has no `React.memo` wrapper, unlike its siblings fixed by #4472 (`TrackTableRowItem`, `ArtistTrackRow`) and #3929/#4177 (`AlbumCard`, `QueueTrackItem`). The prop flow confirms the re-render is real: `CozyArtistList.tsx` recomputes `contextActions` via `useContextMenuActions({ artist: contextMenuArtist, ... })` and holds `contextMenuState` from `useContextMenu()`; both change on every right-click and pass straight through to `ArtistListContent`.
- **Evidence**:
  ```tsx
  // ArtistListItem.tsx — no memo wrapper
  export const ArtistListItem = ({ artist, onClick, onContextMenu }: ArtistListItemProps) => { ... };
  export default ArtistListItem;
  ```
  ```tsx
  // ArtistListContent.tsx:130-139 — rendered directly inside the virtualized row
  <ArtistListItem artist={row.artist} onClick={onArtistClick} onContextMenu={handleContextMenu} />
  ```
- **Impact**: Right-clicking any artist re-renders every artist row currently in the DOM window (~15-30 rows with default `overscan: 8`), not just the target. Reproducible input-latency cost on every context-menu open in a large library — exactly the scenario #3607 was filed for.
- **Siblings**: None — `TrackTableRowItem.tsx:156` and `ArtistTrackRow.tsx:95` both verified still `memo(...)`.
- **Suggested Fix**: Wrap `ArtistListItem` in `React.memo`. `onClick`/`onContextMenu` are already stable `useCallback`s in `CozyArtistList.tsx`, so a plain `memo()` with no custom comparator suffices.

---

### FE-D-1: `index.css` is never loaded — a dead, competing token file that 2 tests and 4 open issues treat as authoritative
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/index.css` (451 lines); `auralis-web/frontend/src/index.tsx:1-20`; `auralis-web/frontend/index.html`; `auralis-web/frontend/src/theme/__tests__/cssCustomPropertyProducers.test.ts:13-16`; `auralis-web/frontend/src/design-system/__tests__/cssVariablesTokenParity.test.ts`
- **Status**: NEW
- **Description**: `src/index.css` defines a complete second design-token system (`--midnight-blue`, `--charcoal`, `--aurora-*`, `--space-*`, `--radius-*`, `--elevation-*`, `--glow-*`, `--transition-*`) plus rules for `body`, `.card`, `.dropzone`, `input[type="text"]`, `h1`-`h4`. None of it reaches the browser: `index.html` has no `<link>` to it and `src/index.tsx` does not import it. `git log -p` shows the import was removed 2025-11-22 in commit `be0f3619` (an unrelated "Paper is not defined" fix) and never restored — dead for ~9 months. Two vitest suites nonetheless read it via `?raw` and assert its values, and `cssCustomPropertyProducers.test.ts:13-16` states "There are exactly two producers of custom properties in this app: `getSemanticCssVariables()` … and the `:root` block in `index.css`" — false; `ThemeContext.tsx` only writes the `--app-*` set.
- **Evidence**:
  ```
  $ git show be0f3619 -- auralis-web/frontend/src/index.tsx
  Date:   Sat Nov 22 19:57:51 2025 -0300
      fix: Defer component imports to resolve 'Paper is not defined' ...
  -import './index.css';
  ```
- **Impact**: The one live CSS Module consuming `index.css`-only variables — `components/player/ShuffleModeSelector.module.css` (`var(--space-md)`, `var(--radius-md)`, `var(--transition-hover-out)`) — would resolve them to nothing if rendered; it is not currently a live bug only because `ShuffleModeSelector.tsx` is itself orphaned. The present-tense damage is to the token system's self-checks: the suite asserts drift-free parity for a file with zero user-visible effect, and four open issues (#3927, #4171, #3636, #4172) describe on-screen color/spacing breakage that cannot be occurring. Anyone trusting those passing tests or issue descriptions is working from a false model of the runtime.
- **Siblings**: None — sole file in this state.
- **Suggested Fix**: Preferably delete `index.css` and its two producer tests, moving the CSS-module-only vars (`--space-*`, `--radius-*`, `--transition-*`) into `globalStyles.ts` so there is exactly one live `:root` producer. Alternatively restore the import and genuinely fix the drift the four issues describe. Either way, retriage #3927/#4171/#3636/#4172 against the outcome.

---

### FE-A-1: Twelve fetch/`.json()` call sites never route through any response guard
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:45-52`, `useLibraryPagination.ts:86-116,162-187`, `useLibraryStats.ts:39-42`, `useLibraryScan.ts:103-138`, `useScanProgress.ts:80-98`, `auralis-web/frontend/src/hooks/fingerprint/useTrackFingerprint.ts:37-47`, `useAlbumFingerprint.ts:29-46`, `useSimilarTracks.ts:175-212`, `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:97-111`, `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:62-89`, `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:45-89`, `useArtistDetailsData.ts:39-71`
- **Status**: NEW
- **Description**: `src/api/responseGuards.ts` exports 8 shape guards and — encouragingly — all 8 *are* wired to a real call site, so the "guard exists but unused" failure mode does not apply to them. What remains unguarded is a second, larger population: each hook above calls raw `fetch()` and casts `response.json()` straight to a TypeScript interface with zero runtime check. (`useMetadataForm` performs an ad-hoc inline `typeof`/`in` check that duplicates rather than reuses the shared mechanism.)
- **Evidence**:
  ```ts
  // hooks/library/useInfiniteAlbums.ts
  const response = await fetch(getApiUrl(`/api/albums?${params}`));
  if (!response.ok) { throw new Error(`Failed to fetch albums: ${response.statusText}`); }
  return response.json();   // no isAlbumsListShape, no shape check at all
  ```
- **Impact**: A backend field rename on any of these 12 endpoints (album/track pagination, library stats, scan, scan status, track/album fingerprint, similarity, now-playing load, metadata, album detail, artist detail) silently degrades to `undefined` in the UI — blank bio field, stuck "0%" scan progress, phantom empty similarity list — instead of failing loudly at the fetch boundary. Exactly the failure class #4607 exists to catch.
- **Siblings**: All 12 above. Related but distinct from OPEN #5026 (which is about *guard* utilization; this is about *call sites* with zero guard involvement).
- **Related**: FE-T-2 (same gap at `useEnhancementControl`), FE-T-4 (same gap on the WS ingestion path).
- **Suggested Fix**: Thread `validate:` through where a guard already exists; add guards to `responseGuards.ts` for the pagination/fingerprint/similarity payloads following the existing `makeListGuard` pattern, wired the way `useLibraryQuery.ts` does.

---

### FE-A-2: Five raw-fetch hooks discard the backend's error `detail` and hand-roll a generic HTTP message
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryStats.ts:40`, `useInfiniteAlbums.ts:47-49`, `auralis-web/frontend/src/components/library/Details/useArtistDetailsData.ts:42-44`, `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:65`, `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:120-130`
- **Status**: NEW
- **Description**: `src/utils/httpError.ts` exists so "every fetch layer in the app" shares one implementation of reading the backend's `HTTPException(detail=...)` before the body is consumed (its own docstring, referencing #4831). `apiRequest.ts` and `useRestAPI.ts` route through it correctly. Four sites above throw a hardcoded, detail-free string on any non-2xx, and `useAppDragDrop.ts` has grown a fourth independent re-implementation of the same logic (`errorFromResponse()`) rather than importing `readHttpErrorBody()`.
- **Evidence**:
  ```ts
  // hooks/library/useLibraryStats.ts:40
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  ```
  ```ts
  // hooks/app/useAppDragDrop.ts:120-130 — 4th independent copy of readHttpErrorBody's job
  async function errorFromResponse(response: Response, fallback: string): Promise<Error> {
    try {
      const errorData = await response.json();
      if (errorData && typeof errorData.detail === 'string' && errorData.detail) {
        return new Error(errorData.detail);
      }
    } catch { /* ... */ }
    return new Error(fallback);
  }
  ```
- **Impact**: A 404 on `/api/library/stats`, `/api/albums`, `/api/artists/{id}`, or `GET /api/metadata/tracks/{id}` surfaces as "HTTP error! status: 404" instead of the backend's actionable detail — the exact class #4831 fixed for `useRestAPI.ts`, recurring in five sites never migrated onto the shared utility.
- **Siblings**: OPEN #4643 (`useAlbumDetails.ts`) and #4626 (fingerprint/similarity fetches) are the same class already filed for other files — not duplicated here.
- **Suggested Fix**: Replace each hand-rolled `if (!response.ok) throw new Error(...)` with `throw await httpErrorFromResponse(response)` from `@/utils/httpError`, and delete `useAppDragDrop.ts`'s local `errorFromResponse()`.

---

### FE-A-3: React Query's app-wide `retry: 1` default blanket-retries every query failure, including 4xx
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/App.tsx:15-23`; consumed without override by `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:84-104`
- **Status**: NEW
- **Description**: The single app-wide `QueryClient` sets `queries: { retry: 1 }` with no status-code discrimination, so every `useQuery`/`useInfiniteQuery` retries once on any thrown error — a 400 (bad `search`/`limit`), a 404, or a 422 gets the same treatment as a transient network blip. `useTrackFingerprint.ts` and `useAlbumFingerprint.ts` were deliberately hardened with `retry: false` ("Don't retry on 404"), direct evidence the team knows this is wrong; `useInfiniteAlbums.ts` has no such override.
- **Evidence**:
  ```ts
  // App.tsx
  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 1000 * 60 * 5, refetchOnWindowFocus: false, retry: 1 } },
  });
  ```
- **Impact**: A 422 or 404 on the album grid triggers one extra doomed request before the error surfaces. Capped at MEDIUM (not HIGH) — a single retry, not a storm, and the app is localhost-bound.
- **Siblings**: Any `useQuery`/`useInfiniteQuery` without its own `retry`; the fingerprint hooks show the correct opt-out.
- **Related**: OPEN #4467 (retry eligibility judged by message substring, not status code) — same root concern, different mechanism.
- **Suggested Fix**: Replace the bare number with a status-aware predicate, e.g. `retry: (count, err) => count < 1 && !isNonRetryableStatus(err)`, reusing `useRestAPI`'s httpError-based status extraction.

---

### FE-Y-1: Album Detail and Artist Detail views render zero `<h1>` elements
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Views/LibraryViewRouter.tsx:65-72,85-94`, `auralis-web/frontend/src/components/library/Details/AlbumDetailView.tsx`, `auralis-web/frontend/src/components/library/Details/ArtistDetailView.tsx`, `auralis-web/frontend/src/components/library/Details/DetailViewHeader.tsx:82-93`, `auralis-web/frontend/src/components/core/AppTopBar.styles.ts:57-70`
- **Status**: NEW
- **Description**: #5013 fixed a *two*-`<h1>` bug by demoting `AppTopBar`'s title to a plain `<div>` and designating `ViewContainer.tsx` (`variant="h3" component="h1"`) the **sole** source of the page `<h1>` — its styles comment says "ViewContainer.tsx already renders the sole `<h1>` for every library view." That premise is false: `LibraryViewRouter.tsx` routes Album Detail and Artist Detail directly to `AlbumDetailView`/`ArtistDetailView`, bypassing `ViewContainer` entirely. Both build their header via `DetailViewHeader`, whose `Title` is `variant="h2"` with no `component` override. Result: **zero `<h1>` on the page**. The `singleH1PerView.test.tsx` regression suite only exercises `AppTopBar` + `ViewContainer` and never renders these two views, so the combination has no coverage.
- **Evidence**:
  ```tsx
  // LibraryViewRouter.tsx:65-72 — Album detail bypasses ViewContainer
  if (selectedAlbumId !== null) {
    return <AlbumDetailView albumId={selectedAlbumId} onBack={onBackFromAlbum} />;
  }
  ```
  ```ts
  // AppTopBar.styles.ts:57-63
  // Not a heading (#5013): ViewContainer.tsx already renders the sole <h1> for every library view ...
  ```
- **Impact**: Screen-reader users navigating by heading level get no page-title landmark on two of the app's most content-dense views; the highest heading present is `<h2>`. The list views (Songs/Albums/Artists/Playlists) are correct via `ViewContainer`.
- **Siblings**: Both detail views share the identical root cause — the same `DetailViewHeader`, with no `<h1>` upstream in either tree.
- **Suggested Fix**: Give `DetailViewHeader`'s `Title` a `component="h1"` override, or wrap both views in a landmark supplying the `<h1>` as `ViewContainer` does. Extend `singleH1PerView.test.tsx` to render `AlbumDetailView`/`ArtistDetailView` directly.

---

### FE-P-2: Artist-detail "Tracks" tab renders the full track array with no virtualization
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Views/TracksTab.tsx:47-66`
- **Status**: NEW
- **Description**: Every other large collection view (album grid, artist list, main track list, queue panel) was deliberately windowed via `useVirtualizer`/`useGridVirtualizer` (#3606/#3607/#3928/#3576). `TracksTab` — all tracks for one artist in the artist-detail view — `.map()`s the full array into `ArtistTrackRow` unconditionally.
- **Evidence**:
  ```tsx
  <TableBody>
    {tracks.map((track, index) => (
      <ArtistTrackRow key={track.id} track={track} index={index} ... />
    ))}
  </TableBody>
  ```
- **Impact**: Bounded by one artist's track count, so fine for the common case. It stops being fine for the buckets a real large library produces — "Various Artists"/"Unknown Artist" normalization buckets, prolific back catalogs, box-set credits — any of which can hold thousands of tracks. `ArtistTrackRow` is memoized (#4472), capping *re-render* cost but not *initial mount*: opening such an artist creates one DOM row + one fiber per track synchronously.
- **Siblings**: `AlbumTrackTable.tsx` has the same unwindowed `.map()` but is inherently bounded by one album's track count — not reported.
- **Suggested Fix**: Reuse the `useVirtualizer` + external-scroll pattern from `TrackListViewContent.tsx`/`ArtistListContent.tsx`, or cap/paginate above a track-count threshold.

---

### FE-P-3: QueueSearchPanel renders filtered results unvirtualized and unmemoized
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/player/QueueSearchPanel/QueueSearchPanel.tsx:202-211`, `auralis-web/frontend/src/components/player/QueueSearchPanel/SearchResultItem.tsx:12-84`
- **Status**: NEW
- **Description**: `useQueueSearch(queue)` returns every queue track matching the active text query and/or duration filter; it is documented as handling "10k tracks" and the sibling `useQueueRecommendations.ts:93-94` documents the queue growing to "1000 tracks (risky)". `QueueSearchPanel` renders `filteredTracks` with a plain `.map()` — no virtualization, unlike `QueuePanelExpanded` which windows the same queue data — and `SearchResultItem` has no `React.memo`.
- **Evidence**:
  ```tsx
  // QueueSearchPanel.tsx:202-211
  <ul style={styles.resultsList}>
    {filteredTracks.map((result) => (
      <SearchResultItem key={`${result.track.id}-${result.originalIndex}`}
        result={result} onSelect={onTrackSelect} onRemove={() => handleRemoveTrack(result)} />
    ))}
  </ul>
  ```
- **Impact**: Clicking a duration-filter chip ("Short (<3m)") with no search text is a one-click way to render every matching queue track at once. On a queue near the documented 1000-track ceiling with a bucket matching a large fraction, this mounts hundreds of unvirtualized, unmemoized rows in one synchronous render, each with local hover state and a freshly-created `onRemove` closure. A user-triggered UI-jank spike.
- **Siblings**: None — the one queue-rendering surface that isn't windowed.
- **Suggested Fix**: Apply `useVirtualizer` to the results `<ul>` (fixed-height overlay, so an internal scroll container is straightforward) and wrap `SearchResultItem` in `React.memo`. A simple "show first 100 matches" cap removes the worst case cheaply if virtualizing is deferred.

---

### FE-R-1: `handleChunk`'s decode-error path omits `trackId`, bypassing the #4434 stale-stream guard
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useAudioStreamingCore.ts:365-369`
- **Status**: NEW
- **Description**: `playerSlice.setStreamingError`'s reducer applies the #4434 staleness guard **only when the action carries a `trackId`**:
  ```ts
  // store/slices/playerSlice.ts:402-417
  if (action.payload.trackId != null && s.trackId !== action.payload.trackId) return;
  ```
  `handleChunk` is the per-chunk hot path #4434 exists for, and its three sibling dispatches in the same file all pass `trackId: message.data.track_id` with an explicit `// drop stale updates after a skip (#4434)` comment. The PCM-decode `catch` block does not, despite `message.data.track_id` being in scope two lines earlier. The #4563 stream-epoch check earlier in `handleChunk` covers **seek** but not **skip** (no epoch bump on track change) and degrades to pre-#4563 behaviour when an older backend omits epoch on the wire.
- **Evidence**:
  ```ts
  // hooks/enhancement/useAudioStreamingCore.ts:365-369
  } catch (error) {
    const errorMsg = `Failed to process audio chunk: ${...}`;
    console.error(logPrefix, errorMsg);
    dispatch(setStreamingError({ streamType, error: errorMsg }));   // <- no trackId
  }
  ```
- **Impact**: A decode error on a frame from a track the user already skipped away from marks the **new**, currently-playing stream `'error'` in Redux, surfacing a spurious "Streaming error" on a stream that is actually fine.
- **Siblings**: `useEnhancedPlayCommand.ts:162` and `useEnhancedStreamStart.ts:218` share the shape (lower risk — command-initiation time, not the per-chunk hot path). `useAudioStreamingCore.ts:218-223`'s watchdog omits it too but is safe: `armStreamStartWatchdog()` unconditionally clears any pending timer at entry.
- **Suggested Fix**: Add `trackId: message.data.track_id` to the `dispatch(setStreamingError(...))` in `handleChunk`'s catch block, matching the three sibling dispatches in the same file.

---

### FE-H-1: Outgoing WebSocket message queue during disconnect has no bound
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:73-74,262-283,321-355`; drained by `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:290-322`
- **Status**: NEW
- **Description**: `useWebSocketConnection` queues every outgoing command sent while disconnected (`send()`, and separately `reissueActiveStreamAs()`) into `messageQueueRef.current`, an array with no size cap, no de-duplication by message type, and no drop policy. `replayQueueAndResume()` `shift()`s and sends the entire backlog on the next successful `open`.
- **Evidence**:
  ```ts
  const messageQueueRef = useRef<OutgoingWebSocketMessage[]>([]);
  ...
  } else {
    console.warn('WebSocket not connected, queueing message');
    messageQueueRef.current.push(message);   // <-- unbounded
  }
  ```
- **Impact**: The backend can be unreachable for the full exponential-backoff window (up to 10 attempts × up to 30 s, i.e. several minutes). Repeated seeks while scrubbing, rapid play/pause, or volume drags each queue one message with nothing capping growth. On reconnect the whole backlog replays sequentially against the freshly-restored stream — the user sees a burst of stale seeks/volume changes instead of only the latest intent taking effect. Memory growth is bounded only by how many UI events fire during the outage.
- **Siblings**: None — the sole outbound queue in the WS stack. `pendingChunksRef`/`pendingMeta` are inbound and cleared on every stream (re)start.
- **Suggested Fix**: Cap `messageQueueRef` (drop-oldest) and/or collapse same-type control messages (`seek`, `volume_changed`) to the most recent instance before replay, mirroring the `queueHadStreamCommand` supersession logic already present for `play_enhanced`/`play_normal`/`stop`/`pause` in `replayQueueAndResume()`.

---

### FE-C-2: `EditMetadataDialog`'s auto-close `setTimeout` is not cancelled on unmount
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/EditMetadataDialog/EditMetadataDialog.tsx:53-61`
- **Status**: NEW
- **Description**: `handleSave` schedules a bare `setTimeout(() => onClose(), 1000)` after a successful save, with no `clearTimeout` and no ref tracking. The parent mounts the dialog conditionally on `editingTrackId` (`{editingTrackId && <EditMetadataDialog .../>}` in `CozyLibraryView.tsx:277-286`) and `handleCloseEditDialog` sets it to `null` — a real unmount, not an MUI `open={false}` hide. Every async fetch in the sibling hook `useMetadataForm.ts` is correctly unmount-guarded (`saveAbortRef`/`AbortController`, #4175/#3601); this component-level timer was missed by that pass.
- **Evidence**:
  ```tsx
  const handleSave = async () => {
    const result = await saveMetadata();
    if (result) {
      setTimeout(() => { onClose(); }, 1000);   // never cleared
    }
  };
  ```
- **Impact**: A user who saves, then within ~1 s cancels and reopens the dialog for a *different* track, has the new dialog spuriously closed by the stale timer. No data loss, but a surprising glitch a user would report as "the metadata dialog randomly closes."
- **Siblings**: None — grepped `setTimeout` across `playlist/`, `settings/`, `shared/SimilarTracksModal/`; no other dialog uses a delayed auto-close.
- **Suggested Fix**: Track the timeout id in a `useRef` and clear it in a `useEffect` cleanup (and in `handleClose`).

---

### FE-T-2: `useEnhancementControl`'s enhancement-status fetch skips the established `validate` guard
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:118-133`
- **Status**: NEW
- **Description**: `useRestAPI().get<T>()` supports an opt-in `validate: (value: unknown) => boolean` specifically so a renamed/retyped backend field surfaces as a located error rather than a silent `undefined` (#4607, generalized in #4896). `useLibraryQuery`, `useQueueFetch`, and `libraryService.getArtistTracks` adopted it. `useEnhancementControl` — enhancement settings, shared across every mounted `EnhancementPane`/`AlbumCharacterPane` via the module-level `_sharedStatusPromise` dedup — passes a bare `getter<EnhancementState>(url)`.
- **Evidence**:
  ```ts
  const promise = getter<EnhancementState>('/api/player/enhancement/status')
    .finally(() => { ... });   // no { validate: ... }
  ```
- **Impact**: Currently benign — the backend's `EnhancementSettings` model (`routers/enhancement.py:101-105`) matches today. But a future rename/nesting (the drift class behind #3593, #3976, #4440, #4441) would make every enhancement UI read `undefined` for `enabled`/`preset`/`intensity` with no error, and `preset` would silently stop being one of the five valid `EnhancementPreset` literals used to select CSS classes and gradients.
- **Siblings**: `auralis-web/frontend/src/hooks/player/useQueueHistory.ts:189-192,228` — same gap, lower traffic.
- **Related**: FE-A-1 (same class, different call sites).
- **Suggested Fix**: Add `isEnhancementStatusShape` to `responseGuards.ts` (checking `enabled: boolean`, `preset: string`, `intensity: number`) and pass it via `{ validate: ... }`.

---

### FE-T-3: `TrackInfo`/`Track`/`TrackApiResponse` declare fields the backend never sends on that channel
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/ws/base.ts:40-69`, `auralis-web/frontend/src/types/domain.ts:12-52`, `auralis-web/frontend/src/api/transformers/types.ts:65-114`
- **Status**: NEW
- **Description**: Two compounding mismatches.
  1. **`loudness` / `crest_factor` (`crestFactor`) / `centroid` never exist on any real payload, REST or WS.** The `Track` ORM model has no such columns — it has `lufs_level`, `peak_level`, `rms_level`, `dr_rating` — and `Track.to_dict()` (the path `serialize_object()` prefers for real ORM rows) emits none of the three. `routers/serializers.py::DEFAULT_TRACK_FIELDS` declares `loudness` but has no `crest_factor`/`centroid` key at all.
  2. **The WS-specific `TrackInfo` over-claims REST-only fields.** The backend's WS `TrackInfo` (`player_state.py:27-50`) is deliberately narrow: `id, title, artist, album, duration, filepath (excluded), artwork_url, format`. The frontend's shared `TrackInfo` — used for `player_state`/`queue_changed`, i.e. `currentTrack` and every queue entry — also declares `genre`, `year`, `bitrate`, `sample_rate`, `bit_depth`, `date_added`, `date_modified`. Those are real REST fields but the WS channel never sends them.
- **Evidence**:
  ```ts
  // src/types/ws/base.ts:40-69
  genre?: string;        // never sent over WS
  loudness?: number;     // never sent anywhere — no such column/key exists
  crest_factor?: number; // never sent anywhere
  centroid?: number;     // never sent anywhere
  ```
  ```python
  # auralis-web/backend/player_state.py:27-50
  class TrackInfo(BaseModel):
      id: int; title: str; artist: str; album: str; duration: float
      filepath: str = Field(exclude=True)
      artwork_url: str | None = None
      format: str | None = None
  ```
- **Impact**: No production consumer currently reads these fields (verified by repo-wide grep), so nothing is visibly broken. It is nonetheless a contract lie in the highest-traffic category (player state / queue / track list): anyone reading `currentTrack.genre` or `track.crestFactor` today gets a silently-wrong `undefined` that type-checks cleanly.
- **Siblings**: The `loudness`/`crestFactor`/`centroid` triple appears in all three type declarations — one root cause.
- **Suggested Fix**: Remove `loudness`/`crest_factor`/`centroid` from all three types (nothing populates or consumes them), or expose real `lufs_level`/`dr_rating`-based fields under honest names. Split the WS-only `TrackInfo` from the REST-oriented fields, or comment the REST-only ones as never present on WS-sourced instances.

---

### FE-D-3: MUI's `sx` numeric spacing shorthand is a second, unmapped spacing scale
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: 45 files under `auralis-web/frontend/src/components/` (87 occurrences); representative: `auralis-web/frontend/src/components/shared/ui/feedback/EmptyState.tsx:77`, `auralis-web/frontend/src/components/settings/PlaybackSettingsPanel.tsx:50,83,100`, `auralis-web/frontend/src/components/shared/ui/loaders/PlayerBarSkeleton.tsx:20-21,39,53`, `auralis-web/frontend/src/components/settings/SettingsDialog.tsx:63,78`. Correct pattern: `auralis-web/frontend/src/design-system/primitives/Stack.tsx:27`
- **Status**: NEW
- **Description**: The design system's own primitives resolve spacing through `tokens.spacing[key]` (named steps `xxs` 2px … `xxxxl` 80px). Elsewhere, 45 component files pass raw numbers to MUI's `sx` (`sx={{ p: 2, mb: 1, gap: 3 }}`), which MUI resolves via its own `theme.spacing(factor)` — an un-customized default 8px grid (`createAuralisTheme()` passes no `spacing:` override). Because `tokens.spacing` is not a clean multiple of 8 at every step (`sm`=6, `lg`=20, `xl`=28, `xxxl`=56), the two scales coincide only by accident: `mt: 2` = 16px has no token equivalent (nearest `md`=12 / `lg`=20); `my: 3` = 24px falls between `lg`=20 and `xl`=28; `mb: 4` = 32px falls between `xl`=28 and `xxl`=40.
- **Evidence**:
  ```tsx
  // design-system/primitives/Stack.tsx — the intended pattern
  const gap = tokens.spacing[spacing];   // 'md' -> 12px

  // components/shared/ui/feedback/EmptyState.tsx:77 — bypasses it
  sx={{ mb: 4 }}   // theme.spacing(4) = 32px, not on tokens.spacing at all
  ```
- **Impact**: Vertical rhythm between MUI-`sx`-styled and `tokens.spacing`/`Stack`-styled components is inconsistent by construction, not by isolated mistake — 87 occurrences across 45 files. This is the "two competing token sources give different values" pattern that sets the MEDIUM bar for this dimension.
- **Siblings**: Full set derivable via `grep -rnoE "\b(m|mt|mb|ml|mr|mx|my|p|pt|pb|pl|pr|px|py|gap):\s*[0-9.]+" src/components`.
- **Related**: FE-D-4 (same root cause for breakpoints).
- **Suggested Fix**: Either pass a `spacing:` resolver to `createTheme()` so MUI's grid resolves through `tokens.spacing`, or add an ESLint rule banning numeric `sx` spacing keys in favour of `tokens.spacing.*` string values (which `sx` already accepts).

---

### FE-Q-1: "Integration" test files mock five non-existent modules from a retired architecture
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/__tests__/Integration.test.tsx:36-149`, `auralis-web/frontend/src/components/__tests__/redux-flow.test.tsx:60-71`
- **Status**: NEW
- **Description**: Both files claim in their docblocks to test "Component interaction with Redux store", "WebSocket message subscriptions", "Real-time updates", and "Component composition", then register `vi.mock()` factories for `@/services/websocket/protocolClient`, `@/hooks/usePlayerCommands`, `@/hooks/usePlayerStateUpdates`, `@/hooks/useQueueCommands`, `@/hooks/useWebSocketProtocol`, and `@/hooks/useStandardizedAPI`. **None of these paths exist** — the real hooks live at `hooks/player/usePlayerStateSync.ts`, `hooks/shared/useStandardizedAPI.ts`, etc. `Integration.test.tsx` also registers `vi.mock('@/contexts/WebSocketContext', ...)` twice (lines 36 and 136) with different shapes; the second silently wins. Only one test in either file calls `render()` (a bare `<ConnectionStatusIndicator />`); everything else dispatches against a hand-built `configureStore` and asserts on `store.getState()` — pure reducer tests with no component and no WebSocket message in play.
- **Evidence**:
  ```ts
  vi.mock('@/hooks/usePlayerCommands', () => ({ usePlayerCommands: () => ({...}) }));
  vi.mock('@/hooks/useWebSocketProtocol', () => ({ ... }));
  // none of these six specifiers resolve to a file on disk
  ```
- **Impact**: A developer reading the docblocks reasonably concludes there is component-level real-time/WebSocket integration coverage for the player and queue UI. There isn't. If the real command/state hooks these dead mocks were modeled on regress, nothing here catches it — and the "Integration Tests" file name makes the gap easy to overlook when scoping new coverage.
- **Siblings**: `redux-flow.test.tsx` has the single dead `vi.mock('@/hooks/useStandardizedAPI')` plus the same reducer-only pattern.
- **Suggested Fix**: Delete the six dead `vi.mock()` calls, collapse the duplicate `WebSocketContext` mock, and either rename both files to reflect what they actually test (Redux slice interplay) or add real `render()`-based assertions for the claims in the docblocks.

---

### FE-Q-2: `TrackRowMemoization.test.tsx`'s ContextMenu mock path is one level too shallow
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/__tests__/TrackRowMemoization.test.tsx:21-23`
- **Status**: NEW
- **Description**: The spec mocks `vi.mock('../../shared/ContextMenu', ...)`. Resolved from `components/library/Items/tracks/__tests__/`, that points at `components/library/Items/shared/ContextMenu` — which does not exist. The real module imported by the component under test is `@/components/shared/ContextMenu` (`TrackRow.tsx:3`), three levels up. The mock is silently orphaned: nothing intercepts the import, and the real `ContextMenu` (with its own `useState`/`useEffect`, `usePlaylistActions`, `playlistService` import, and `CreatePlaylistDialog` subtree) mounts in every "memoization" test. The comment above the mock ("Mock hooks and components to reduce noise in tests") states the opposite of what happens. The sibling `components/library/__tests__/TrackRow.test.tsx` uses the identical specifier and resolves correctly only because it sits one directory shallower — confirming this is specific to the deeper-nested spec, not a project convention.
- **Evidence**:
  ```ts
  // TrackRowMemoization.test.tsx:21
  vi.mock('../../shared/ContextMenu', () => ({ ContextMenu: () => null }));
  // resolves to components/library/Items/shared/ContextMenu — does not exist

  // TrackRow.tsx:3
  import { ContextMenu } from '@/components/shared/ContextMenu';
  ```
- **Impact**: The file's entire purpose is verifying `React.memo` behaviour on `TrackRow` in isolation (#2173, per its own docstring). With the real subtree mounted, that isolation is gone: assertions run against a heavier tree, and any future side effect in `ContextMenu`'s mount path would surface here as a confusing memoization failure. It happens not to crash only because `open={false}` short-circuits visible rendering — a coincidence of props, not a designed boundary.
- **Siblings**: None — verified by a repo-wide script resolving every `vi.mock()` specifier against the filesystem; this is the only relative-path mock with a factory that fails to resolve.
- **Suggested Fix**: Change to `vi.mock('@/components/shared/ContextMenu', () => ({ ContextMenu: () => null }))`.

---

### FE-Q-3: `playlist-management.test.tsx` — rename/delete/duplicate tests pass with the feature deleted
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/library-management/playlist-management.test.tsx:118-186`
- **Status**: NEW
- **Description**: Three tests under "Playlist CRUD Operations" do not verify the behaviour their names claim.
  - **Rename** (118-142): inside a `waitFor` callback, conditionally calls `user.click(editOption)` **without `await`** — a floating promise racing the rest of the test. The final assertion checks only that the *original* label is still present; no renamed text is ever asserted.
  - **Delete** (144-166): asserts `expect(playlist).toBeInTheDocument()` — that the playlist has **not** been deleted — with no call into the delete flow at all.
  - **Duplicate** (168-186): asserts `expect(createSpy).toBeDefined()`; a `vi.spyOn()` return value is always defined.
- **Evidence**:
  ```ts
  // rename — floating promise, no rename ever asserted
  await waitFor(() => {
    const editOption = screen.queryByText(/edit/i);
    if (editOption) { user.click(editOption); }   // <-- missing `await`
  }, { timeout: 1000 });
  expect(playlist).toBeInTheDocument();   // only proves the OLD label is still there

  // duplicate — tautological
  const createSpy = vi.spyOn(playlistService, 'createPlaylist');
  expect(createSpy).toBeDefined();
  ```
- **Impact**: `library-management` is a named critical suite (`test:library`). A real regression in playlist rename, delete, or duplicate — including removing the feature's UI trigger — produces zero failures, giving false confidence that playlist CRUD is covered end-to-end when 3 of ~6 CRUD tests assert nothing meaningful.
- **Siblings**: None — `filter`/`sort`/`search`/`metadata`/`artwork` sibling specs were spot-checked and do not share the pattern.
- **Suggested Fix**: `await` the click; assert the renamed text appears and the deleted label disappears (`waitFor(() => expect(screen.queryByText('Favorites')).not.toBeInTheDocument())`); replace `toBeDefined()` with an assertion that `createSpy` was called with the source playlist's data.

---

### LOW

---

### FE-Y-3: Settings "Remove folder" icon button has no accessible name
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/settings/FoldersList.tsx:70-77`, `auralis-web/frontend/src/design-system/primitives/IconButton.tsx:168-200`
- **Status**: Regression of #4473
- **Description**: The design-system `IconButton`'s `tooltip` prop only wraps the button in an MUI `Tooltip`; it does **not** forward the text into `aria-label`. MUI's `Tooltip` sets `aria-describedby` on hover/focus, not an accessible *name*, and MUI icon components render `aria-hidden` by default without `titleAccess`. So the "Remove folder" button has no accessible name at all. #4473 ("Settings 'remove folder' button — add explicit aria-label") was closed against this exact code; the fix is not in current source.
- **Evidence**:
  ```tsx
  // FoldersList.tsx:70-77
  <IconButton onClick={() => onRemoveFolder(folder)} size="sm"
    tooltip="Remove this folder" sx={{ color: themeVars.error }}>
    <DeleteIcon fontSize="small" />
  </IconButton>
  ```
  ```tsx
  // design-system/primitives/IconButton.tsx:190-197 — tooltip never becomes aria-label
  if (tooltip && !disabled) { return <Tooltip title={tooltip} arrow>{button}</Tooltip>; }
  ```
- **Impact**: A screen-reader user tabbing through Settings → Library folders hears an unlabeled "button" for the per-folder delete control. A sweep of all 17 `<IconButton tooltip=...>` consumers found this to be the **only** site relying solely on `tooltip`.
- **Suggested Fix**: Add an explicit `aria-label` at the call site. Additionally consider having the `IconButton` primitive fall back to `tooltip` as `aria-label` when none is passed, so this class of regression cannot recur silently.

---

### FE-C-1: Four components exceed the 300-line guideline
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/ComfortableApp.tsx` (431), `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx` (390), `auralis-web/frontend/src/components/player/ProgressBar.tsx` (331), `auralis-web/frontend/src/components/library/CozyLibraryView.tsx` (308)
- **Status**: NEW
- **Description**: Verified via `wc -l` against `master` (188db72a). The next-largest in-scope files are already under the line (`AlbumCharacterPane.tsx` 295, `QueuePanelExpanded.tsx` 278), so this is a bounded outlier set, not a fuzzy cutoff.
- **Impact**: Maintainability only. All four were read in full and are well-organized internally (hooks extracted to sibling files, clear section boundaries). No functional defect follows from the size. LOW per the project severity table.
- **Suggested Fix**: Opportunistic. If touched: extract `ComfortableApp.tsx`'s keyboard-shortcut array construction (lines 84-234) into a hook, and split `CozyAlbumGrid.tsx`'s sort/era-group logic out of the render component the way `EraSection.tsx`/`AlbumGridContent.tsx` already are.

---

### FE-R-2: `useAppErrors`/`useConnectionHealth` return unmemoized object literals
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:410-423,428-445`
- **Status**: NEW
- **Description**: Every other combining hook in this file (`usePlayer`, `useQueue`, `useCache`, `useConnection`) wraps its return in `useMemo` for reference stability, each with a `#2537`/`#3619`/`#4176` comment explaining why. These two return a fresh object literal on every render. `useConnectionHealth` additionally duplicates `connectionSlice.selectConnectionHealth`'s logic inline.
- **Evidence**:
  ```ts
  export const useAppErrors = () => {
    const playerError = useSelector((state: RootState) => state.player.error);
    ...
    return { playerError, queueError, cacheError, connectionError, hasErrors: !!(...) };
  };
  ```
- **Impact**: Neither hook has a production call site today (exported from `hooks/shared/index.ts`, exercised only in tests), so no live churn. Latent: the first consumer that passes the result to a `React.memo` child or another hook's dep array silently defeats memoization the exact way the four sibling hooks were fixed to avoid.
- **Suggested Fix**: Wrap both returns in `useMemo`; have `useConnectionHealth` reuse `selectConnectionHealth` instead of re-deriving inline.

---

### FE-H-2: `useMasteringRecommendation`'s per-track cache has no eviction
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useMasteringRecommendation.ts:21-23,32,43-65,94-99`
- **Status**: NEW
- **Description**: `cache = useRef<MasteringRecommendationCache>({})` stores one entry per distinct `trackId` for the lifetime of the consuming component. Entries are only added (on a WS `mastering_recommendation` message) or individually deleted via a caller-invoked `clearRecommendation()`; nothing purges automatically and there is no cap. The same class was fixed elsewhere in this codebase — `useArtworkPalette`'s `paletteCache` (bounded LRU, `MAX_PALETTE_CACHE_ENTRIES = 500`, #5020) and `useSimilarTracks`' `similarityCache` (`CACHE_MAX_ENTRIES = 50`) — but not here.
- **Evidence**:
  ```ts
  cache.current[trackId] = rec;   // never evicted
  ```
- **Impact**: Slow unbounded growth proportional to distinct tracks played in one session. Each entry is a handful of scalars, so this is gradual rather than acute, and fully released on remount/reload. The only production consumer (`AlbumCharacterPane`) is the kind of always-visible panel that plausibly stays mounted for a whole session.
- **Siblings**: None currently unbounded elsewhere in `hooks/enhancement/` or `hooks/fingerprint/`.
- **Suggested Fix**: Cap `cache.current` with the same drop-oldest/LRU pattern used by `paletteCache`/`similarityCache`.

---

### FE-T-1: `any` usage cluster — two real gaps, the rest correctly typed
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: 16 non-test files; the two worth fixing are `auralis-web/frontend/src/a11y/focusManagement.ts:419-420` and `auralis-web/frontend/src/utils/errorHandling.ts:127,140-152`
- **Status**: NEW
- **Description**: All ~70 non-test `any` occurrences were triaged. The large majority are the correct type for what they express: `ComponentType<any>`/`Promise<any>` in the lazy-loading utilities, `Record<string, any>` request-body params (documented, with #4607/#4896's `validate` guard covering the response side), `...args: any[]` on variadic logging wrappers, polymorphic ref forwarding in `Text.tsx`, and several matches that are prose inside comments rather than code.
- **Evidence**:
  ```ts
  // src/a11y/focusManagement.ts:419-420
  if ((element as any).placeholder) { return (element as any).placeholder; }
  ```
  The `errorHandling.ts` `WebSocketManager` casts sit in dead code — the file's own header says its sole importer, `processingService`, was deleted in #4470.
- **Impact**: None of the 70 currently masks a live data-boundary bug. The `focusManagement.ts` pair is the only one touching real DOM data outside dead code, and it degrades gracefully behind a falsy check.
- **Suggested Fix**: Narrow the two `focusManagement.ts` casts to `HTMLInputElement | HTMLTextAreaElement`. Leave the rest — do not chase the `any` count for its own sake here.

---

### FE-T-4: WebSocket text-frame dispatch casts `JSON.parse()` straight to the message union
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:234-238`
- **Status**: NEW
- **Description**: The single entry point for every WebSocket message performs an unguarded assignment-cast — no check that the parsed value is an object, let alone that `.type` is a known literal — while the REST side is trending toward opt-in runtime guards (#4607/#4896).
- **Evidence**:
  ```ts
  const message: AnyWebSocketMessage | WebSocketMessage | AudioChunkMetaMessage = JSON.parse(event.data);
  ```
  Downstream, `checkSeqForDesync(message as AudioChunkMetaMessage, dispatch)` and `dispatchMessage()` both trust `message.type` to key a `Map<WebSocketMessageType, Set<MessageHandler>>`.
- **Impact**: A malformed text frame would either be silently dropped (`undefined` type, no matching dispatch key, no error) or throw a `TypeError` inside `onmessage` (`JSON.parse('null')`). Given a desktop app talking only to its own bundled localhost backend, this is a defense-in-depth gap, not an active bug.
- **Related**: FE-A-1, FE-T-2 (same response-validation family).
- **Suggested Fix**: A minimal `typeof message === 'object' && message !== null && typeof message.type === 'string'` guard before touching `.type`, dropping the frame with a `console.warn` otherwise.

---

### FE-D-2: Raw hex colour literals bypass tokens in two files
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts:62-67,215,221`; `auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css:59,86`
- **Status**: NEW
- **Description**: After triaging every raw hex/rgb/rgba/hsl hit outside `design-system/` and `theme/`, the only genuine bypasses are `loggerMiddleware.ts`'s console colour map and two literal `rgba()` box-shadows in `ShuffleModeSelector.module.css`. Everything else matching the regex is either a comment documenting a token's hex value, or legitimate audio-driven `hsla(hue, ...)` visualization math where `hue` derives from track data.
- **Evidence**:
  ```ts
  const colors = { action: '#03A9F4', prevState: '#9C27B0', nextState: '#4CAF50', error: '#F20404', duration: '#FF6D00' };
  ```
- **Impact**: `loggerMiddleware.ts` is gated on `import.meta.env.DEV` and styles only DevTools console output — never rendered UI. The CSS-module hits are inert because that component is not rendered anywhere (see FE-D-1).
- **Related**: FE-D-1.
- **Suggested Fix**: Low priority. If touched, route the console colours through `tokens.colors.semantic.*`/`accent.*` and replace the two `rgba()` literals with `--app-*` custom properties once `ShuffleModeSelector` is either wired in or removed.

---

### FE-D-4: MUI theme breakpoints are never wired to `tokens.breakpoints`
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:152-192`; consumers `auralis-web/frontend/src/components/core/AppTopBar.tsx:105`, `auralis-web/frontend/src/components/core/AppSidebar.tsx:97`, `auralis-web/frontend/src/hooks/app/useAppLayout.ts:51,53`
- **Status**: NEW
- **Description**: `design-system/tokens/layout.ts` defines a `breakpoints` scale intended as the single source of truth, but `createAuralisTheme()` never passes a `breakpoints:` option to `createTheme()`. Every `useMediaQuery(theme.breakpoints.down('md'))` therefore resolves against MUI's own hardcoded defaults. The values happen to be numerically identical today (both 0/600/900/1200/1536), so there is no live drift.
- **Evidence**:
  ```tsx
  return createTheme({ cssVariables: false, palette: {...}, typography: {...} });
  // no `breakpoints: { values: tokens.breakpoints }`
  ```
- **Impact**: Latent-drift risk only. The next person to change `tokens.breakpoints.md` for a design reason will not get the behaviour change they expect from MUI-driven responsive components, while the raw CSS `@media` queries that *do* reference the token (`DetailViewHeader.tsx`, `Player.styles.ts`, `TrackRow.styles.ts`) will shift — producing a split-brain layout.
- **Related**: FE-D-3 (same root cause for spacing).
- **Suggested Fix**: Pass `breakpoints: { values: { ... } }` derived from `tokens.breakpoints` to the `createTheme()` call.

---

### FE-A-4: Ten call sites hand-roll relative URL strings instead of `getApiUrl()`/`ENDPOINTS`
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryStats.ts:39`, `useLibraryScan.ts:103`, `useScanProgress.ts:80`, `auralis-web/frontend/src/hooks/shared/useAPIHealthPoll.ts:30`, `auralis-web/frontend/src/hooks/app/useAppDragDrop.ts:140,165,189,214`, `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:62,131`, `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:45,101`, `useArtistDetailsData.ts:39`
- **Status**: NEW (same class as closed #3988, which fixed a different set of files — those three remain fixed)
- **Description**: `src/config/api.ts` centralizes the base URL with `VITE_API_URL`/`VITE_WS_URL` overrides (#4468) so no call site needs to know whether it is talking to the Vite dev proxy or the packaged app's `http://localhost:8765`. These ten call `fetch('/api/...')` with a bare literal; several of the literals even have unused matching `ENDPOINTS.*` constants already defined (`LIBRARY_STATS`, `LIBRARY_SCAN`).
- **Evidence**:
  ```ts
  // useLibraryStats.ts:39 — ENDPOINTS.LIBRARY_STATS exists and is unused
  const response = await fetch('/api/library/stats', { signal: controller.signal });
  ```
- **Impact**: Harmless today — in dev the page is served from the Vite origin with an `/api/*` proxy, and in the packaged Electron app the backend serves the built frontend from the same origin. The risk is latent: if `VITE_API_URL` is ever pointed off-origin (the escape hatch #4468 added for exactly this), these ten silently keep hitting the old origin while every other call site follows the override.
- **Siblings**: All ten; `useAppDragDrop.ts` alone accounts for four.
- **Suggested Fix**: Route each through `getApiUrl()` or the matching `ENDPOINTS.*` constant.

---

### FE-A-5: `useInfiniteAlbums`'s `queryFn` ignores TanStack Query's cancellation `signal`
- **Severity**: LOW
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:27-53,86-96`
- **Status**: NEW
- **Description**: TanStack Query passes `{ queryKey, pageParam, signal }` into `queryFn` and aborts that signal on cancellation (unmount, key change, supersession). `fetchAlbums()` destructures only `pageParam` and never forwards `signal` to `fetch()` — unlike every other data-fetching hook in scope (`useLibraryPagination`, `useLibraryStats`, `useAlbumDetails`, `useArtistDetailsData`, `useMetadataForm`, `useRestAPI`), all of which wire an AbortController.
- **Evidence**:
  ```ts
  queryFn: async ({ pageParam }) => { /* signal available on this arg object, unused */ }
  ```
- **Impact**: A stray in-flight `/api/albums` request survives past the point React Query stopped caring — wasted work on the single-process localhost ASGI loop, not a correctness bug since the result is discarded.
- **Siblings**: None — the only `queryFn` in scope that doesn't forward its signal.
- **Suggested Fix**: Accept `signal` in `fetchAlbums`'s parameter object and pass it to `fetch(url, { signal })`.

---

### FE-Y-2: `ClearQueueDialog` hand-rolls its own focus trap instead of using the shared `a11y` module
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/ClearQueueDialog.tsx:14-38`
- **Status**: NEW
- **Description**: The codebase has a sanctioned, tested focus trap — `focusManager.createFocusTrap()` in `src/a11y/focusManagement.ts`, consumed via `useDialogAccessibility` — which `ConfirmationDialog.tsx` and `QueueSearchPanel.tsx` both use correctly. `ClearQueueDialog.tsx` re-implements the identical logic inline: its own `handleKeyDown` does Tab/Shift+Tab cycling via a manual `querySelectorAll(...)`, plus a separate effect that manually restores focus to `triggerRef.current`.
- **Evidence**:
  ```tsx
  const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  ```
  Contrast: `const dialogRef = useDialogAccessibility(onCancel, isOpen);`
- **Impact**: No user-visible breakage today, but a maintenance hazard for a11y-critical code — a future refinement to `focusManager.createFocusTrap()` (handling `inert`, `aria-hidden` siblings, dialog stacking) will not reach this dialog.
- **Siblings**: None — the only hand-rolled instance in `components/`.
- **Suggested Fix**: Replace the inline logic with `useDialogAccessibility(onCancel)`.

---

### FE-Q-4: `SettingsDialog.test.tsx` — close/cancel tests use assertions that cannot fail
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/components/settings/__tests__/SettingsDialog.test.tsx:73-79,88-96,98-110`
- **Status**: NEW
- **Description**: Three tests assert nothing that distinguishes working from broken:
  - `should have close button`: `expect(closeButtons.length).toBeGreaterThanOrEqual(0)` — `.length` is never negative.
  - `should call onClose when close button is clicked`: the only assertion is nested inside `if (closeButtons.length > 0)`, so a regressed accessible name means the body never runs and Vitest reports a pass with zero assertions.
  - `should call onClose when Cancel is clicked`: same guard, and **no assertion inside the body at all** — only the comment `// onClose may or may not be called depending on implementation`.
- **Evidence**:
  ```ts
  it('should have close button', () => {
    const closeButtons = screen.queryAllByRole('button', { name: /close/i });
    expect(closeButtons.length).toBeGreaterThanOrEqual(0);   // always true
  });
  ```
- **Impact**: Lower severity than FE-Q-3 — `SettingsDialog` is a secondary surface and other tests in the file do assert real behaviour. Still, a regression removing the buttons' accessible names or breaking the `onClose` wiring is caught by none of these three.
- **Suggested Fix**: Use `screen.getByRole(...)` (throws when absent) instead of `queryAllByRole` + conditional guard, and assert `expect(onClose).toHaveBeenCalledTimes(1)` unconditionally.

---

## Relationships

**Shared root cause — "the utility exists, the migration didn't finish"** (12 findings):

| Canonical utility | Adopted by | Unmigrated (finding) |
|---|---|---|
| `api/responseGuards.ts` + `validate:` option | libraryService, playlistService, queueService, settingsService, useQueueFetch, useLibraryQuery | 12 raw-fetch hooks (**FE-A-1**), `useEnhancementControl` (**FE-T-2**), the WS ingestion point (**FE-T-4**) |
| `utils/httpError.ts` | `apiRequest.ts`, `useRestAPI.ts` | 5 hooks (**FE-A-2**) — plus OPEN #4643, #4626 for other files |
| `config/api.ts` `getApiUrl()`/`ENDPOINTS` | most call sites, incl. #3988's three | 10 call sites (**FE-A-4**) |
| `a11y/focusManagement.ts` via `useDialogAccessibility` | ConfirmationDialog, QueueSearchPanel | ClearQueueDialog (**FE-Y-2**) |
| `React.memo` on list rows (#4472, #3929, #4177) | TrackTableRowItem, ArtistTrackRow, AlbumCard, QueueTrackItem | ArtistListItem (**FE-P-1**), SearchResultItem (**FE-P-3**) |
| `useVirtualizer` on large lists (#3606/#3607/#3928/#3576) | album grid, artist list, track list, queue panel, track cache list | TracksTab (**FE-P-2**), QueueSearchPanel (**FE-P-3**) |
| `useMemo` on combining-hook returns (#2537/#3619/#4176) | usePlayer, useQueue, useCache, useConnection | useAppErrors, useConnectionHealth (**FE-R-2**) |
| Bounded LRU on hook caches (#5020) | useArtworkPalette, useSimilarTracks | useMasteringRecommendation (**FE-H-2**) |
| `trackId` on `setStreamingError` (#4434) | handleStreamEnd, handleStreamError, updateStreamingProgress | handleChunk's catch (**FE-R-1**) |

The practical implication: a per-site fix closes one finding, but the pattern
recurs because nothing structurally prevents a new call site from skipping the
utility. Where a lint rule or a wrapper-only API is feasible (`getApiUrl`,
`sx` spacing, `IconButton` aria fallback), that is worth more than the individual
fixes.

**Design-system duality** — **FE-D-3** (MUI `sx` spacing) and **FE-D-4** (MUI
breakpoints) are the same root cause: `createTheme()` in `theme/themeConfig.ts`
is never given the token scales, so MUI's defaults silently coexist with
`tokens.*`. One fix in `createAuralisTheme()` addresses both.

**Dead-code-that-looks-live** — **FE-D-1** (`index.css`), **FE-Q-1** (mocks of
deleted modules), **FE-Q-2** (mock path that never resolves), and the already-open
#4696 (`performance/` toolkit) are all the same failure mode: an artifact whose
existence implies coverage or effect it does not have. **FE-D-2**'s CSS-module
hits are inert *because* of FE-D-1.

**Closed-but-not-fixed** — **FE-P-1** (#3607) and **FE-Y-3** (#4473). Both were
closed as fixed; neither fix is in current source. Worth a broader spot-check of
recently-closed frontend issues.

---

## Prioritized Fix Order

**Tier 1 — verify first (closed issues whose fix is missing; minutes each)**
1. **FE-P-1** — add `React.memo` to `ArtistListItem`. One line; closes the
   unfinished half of #3607 and removes a per-right-click render storm.
2. **FE-Y-3** — add `aria-label` to `FoldersList.tsx`'s remove button, and make
   `IconButton` fall back to `tooltip` so it cannot silently recur.

**Tier 2 — false confidence (fix before it misleads more work)**
3. **FE-D-1** — decide `index.css`'s fate (delete preferred), then retriage
   #3927/#4171/#3636/#4172 against the outcome. Four open issues currently
   describe impossible symptoms.
4. **FE-Q-3** — the three vacuous playlist CRUD tests, in a named critical suite.
5. **FE-Q-1**, **FE-Q-2** — dead mocks and the orphaned mock path.

**Tier 3 — correctness gaps with real user-visible effects**
6. **FE-R-1** — one-line `trackId` addition; removes spurious streaming errors
   after a skip.
7. **FE-Y-1** — `component="h1"` on `DetailViewHeader`'s title, plus extending
   `singleH1PerView.test.tsx` to cover the two detail views.
8. **FE-C-2** — clear the `EditMetadataDialog` timer on unmount.
9. **FE-H-1** — cap and de-duplicate the outbound WS queue.

**Tier 4 — systemic hardening (do as a batch, not one at a time)**
10. **FE-A-1** + **FE-T-2** + **FE-T-4** — one pass adding the missing guards
    across all unguarded response boundaries, REST and WS.
11. **FE-A-2** + **FE-A-4** — one pass migrating the remaining call sites onto
    `httpError.ts` and `getApiUrl()`; delete `useAppDragDrop.ts`'s duplicate.
12. **FE-A-3** — status-aware retry predicate on the app-wide `QueryClient`.
13. **FE-D-3** + **FE-D-4** — wire `tokens.spacing` and `tokens.breakpoints`
    into `createAuralisTheme()`; consider the accompanying lint rule.

**Tier 5 — scale-dependent and opportunistic**
14. **FE-P-2**, **FE-P-3** — virtualize the two remaining unwindowed lists.
15. **FE-T-3** — remove or honestly rename the phantom track analysis fields.
16. **FE-R-2**, **FE-H-2**, **FE-T-1**, **FE-D-2**, **FE-A-5**, **FE-Y-2**,
    **FE-Q-4**, **FE-C-1** — fix when adjacent code is touched.

---

## Verified Clean (checked, no finding)

Recorded so a future audit does not re-derive them:

- **Streaming/WS core** — stream-epoch guards (#4563/#3774), `seq` desync
  detection, binary PCM/Blob frame pairing (#4331), flow-control hysteresis
  (75%/50%), StrictMode double-mount singleton, ping/pong keepalive, and
  complete cleanup of every `setInterval`/subscription in `src/hooks/`.
- **Redux store** — all cross-slice selectors wrapped in `createSelector`; no
  non-serializable state; every `createAsyncThunk` has a `.rejected` case;
  #4836 (stale queue rollback) and #3587/#4580 (currentTrack divergence) still fixed.
- **Type safety** — `pnpm run type-check:prod` clean (0 errors); the 107
  `type-check` errors are all in `__tests__` and consistent with the documented
  `noUncheckedIndexedAccess` baseline (#4665); WS message union has a
  compile-time `_AssertExhaustive` check.
- **Performance** — `position_changed` is a 1 Hz tick, not 20 Hz; streaming
  progress is decile-throttled (#2535); the visualizer is capped at 30 fps;
  heavy views are behind `React.lazy`; artwork requests sized thumbnails
  (#4447) with `loading="lazy"`; audio buffers are disposed in `cleanupStreaming()`.
- **Accessibility** — #4474 (play/pause announcement) and #2362 (track-change
  announcement) both still present and independent; ProgressBar/VolumeControl
  have complete slider ARIA; all dark- and light-mode text tokens clear WCAG AA
  except `text.disabled`, which is exempt and guarded by #4635's allowlist test;
  the keyboard-reachability sweep found only decorative backdrop handlers.
- **Test suite** — `src/test/setup.ts`'s WebSocketContext auto-mock is a
  complete 9/9-field match against the real interface; all 7 specs exercising
  the real WebSocketContext correctly `vi.unmock()`; no unbounded mock loops or
  OOM hazards; no snapshot usage anywhere.
- **Imports** — 0 non-test relative `../../` imports; `@/` convention holds.
- **Retired architecture** — confirmed absent, not merely unreported: no
  `EnhancementContext`, no fingerprint-server client, no `LibraryManager` usage.

## Existing Issues Confirmed Still Accurate (not re-filed)

#4696 (`performance/` toolkit dead code), #4877 (103 files read dark-only tokens
instead of `themeVars`), #4608 (`useAudioStreamingCore` unmemoized return),
#4459, #5009, #4629, #4921, #5016, #5017, #5026, #5019, #4693, #4694, #4467,
#4643, #4626, #4486, #5102.

---

*Generated by `/audit-frontend` as part of the `comprehensive` audit suite.
Publish with:* `/audit-publish docs/audits/AUDIT_FRONTEND_2026-08-13.md`
