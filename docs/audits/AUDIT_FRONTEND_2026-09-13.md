# Frontend Audit — 2026-09-13

**Scope**: `auralis-web/frontend/src/` — components, Redux store, hooks, contexts, services/API layer, types, design system, accessibility, test suite and CI baseline gate.
**Method**: Fresh audit of the current working tree (HEAD `ce119be1` plus the user's uncommitted edits to `settingsService.ts` / `serviceFactory.ts`, audited as they stand). Nine dimension agents ran in parallel (max 3 at a time). The orchestrator then checked every MEDIUM finding and every claim that affected severity against the source before merging. Dedup ran against all 1,500 GitHub issues (open and closed).
**Depth**: deep | **Limit**: none
**Context**: `pnpm run type-check:prod` is clean (0 errors). `auralis-web/frontend/test-baseline.json` lists 108 known failures. The 2026-09-13 narrowing of enhancement presets to `'adaptive'` (commits `c195ac80`, `ae9d28e3`) is intentional and was **not** treated as a regression. Every preset mirror (`types/domain.ts`, `types/ws/enhancement.ts`, `playerSlice.ts`, `usePlayerStateSync.ts` `VALID_PRESETS`, `useEnhancementControl.ts`) was checked and agrees. No production request sends a removed preset name.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 5 |
| LOW      | 18 |
| **Total**| **23** |

**Overall picture.** The frontend is mature. Most checklist areas came back clean, with visible regression guards for earlier issues:
- The WebSocket singleton and reconnect handling.
- Seq watermarks against out-of-order player events.
- Generation counters on optimistic queue mutations.
- A single shared `AudioContext` and enhanced-audio session (#4541).
- Virtualization of every large list.
- Per-icon MUI imports.
- Buffer disposal on track change (#4147, #4869).
- Theme-aware tokens (#4877).
- Correct `vi.unmock` discipline for the globally mocked `WebSocketContext`.

No CRITICAL or HIGH defects were found.

**Key themes**
1. **Runtime response guards don't cover everything they claim to.** `responseGuards.ts` covers most endpoints, but the main library track list (`useLibraryPagination`) and album detail (`useAlbumDetails`) bypass it. The #5026 comment claiming full coverage is wrong (FE-03, FE-04).
2. **Error-detail contract mismatch.** `httpError.ts` renders FastAPI's *default* 422 `detail` array. The backend installs a custom handler that sends `{detail: "Validation error", errors: [{field, message}]}`, and no frontend code reads `errors`. Field-level validation messages never reach the user (FE-05).
3. **Keyboard focus on the main track list.** In `TrackRow`, the play and more-options buttons can take Tab focus but stay at `opacity: 0` when focused (FE-01).
4. **CI gate honesty.** The frontend baseline ratchet has no stale-entry detection, unlike the backend's `--strict-stale` (#5091), and already carries one stale entry (FE-02).
5. **Dead or parallel surfaces left behind by earlier refactors.** Examples: unwired Redux `isLoading`/`error` fields, dead combinator hooks, a second `usePlaybackProgress`, unused `domain.ts` types, a dead retry module and dead AudioContext wiring. Each is LOW, but together they are the main maintainability tax.

**Most impactful to fix first**: FE-01 (WCAG 2.4.7 on the busiest view, a small CSS fix), FE-03 (the silent empty-library failure mode on the main view), FE-05 (validation errors are unreadable), FE-02 (the gate can re-permit fixed failures).

---

## Findings

### MEDIUM

### FE-01: TrackRow's play and more-options buttons are invisible while they hold keyboard focus
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts:66-68,84-88,121-142,238-257`; rendered by `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.tsx:131,158-165` and `auralis-web/frontend/src/components/library/Items/tracks/TrackRowPlayButton.tsx:29`
- **Status**: NEW
- **Description**: `PlayButton` and `MoreButton` are MUI `IconButton`s, tabbable by default (no `tabIndex={-1}`), styled `opacity: 0`. The only rule that reveals them is `RowContainer`'s `&:hover` (`'& .play-button' / '& .more-button': { opacity: 1 }`). `RowContainer`'s `&:focus-visible` only draws an outline on the row. Neither button has a `:focus-visible` / `.Mui-focusVisible` rule. Tabbing from a row onto its play or more button puts focus on an invisible control. `TrackRow` is live: `TrackListViewContent` → `SelectableTrackRow` → `TrackRow`, which is the Songs/Favourites/Recent/Playlists list. The sibling controls already handle this. `TrackTableRowItem.tsx:109-111` uses `'.MuiTableRow-root:hover &, &:focus-visible': { opacity: 1 }`, and `SelectableTrackRow.styles.ts:39` reveals the checkbox on `.Mui-focusVisible`.
- **Evidence**:
  ```ts
  // TrackRow.styles.ts
  export const PlayButton = styled(IconButton)({ ..., opacity: 0, ... '&:hover': {...} });   // no focus rule
  export const MoreButton = styled(IconButton)({ ..., opacity: 0, ... '&:hover': {...} });   // no focus rule
  // RowContainer
  '&:hover': { '& .play-button': { opacity: 1 }, '& .more-button': { opacity: 1 } },
  '&:focus-visible': { outline: `2px solid ${themeVars.accent}`, outlineOffset: '2px' },    // does not reveal children
  ```
- **Impact**: Keyboard users lose sight of focus for two tab stops on every row of the main track list (fails WCAG 2.4.7 Focus Visible). Activation still works, but users can't see what they are about to trigger.
- **Siblings**: Only `PlayButton` and `MoreButton` in this file. `TrackTableRowItem` and the `SelectableTrackRow` checkbox are already correct.
- **Suggested Fix**: Add `'&:focus-visible, &.Mui-focusVisible': { opacity: 1 }` to both styled buttons. Optionally reveal both on `RowContainer:focus-within` so they appear as soon as focus enters the row.

### FE-02: Frontend baseline ratchet cannot detect stale entries, and already carries one
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/scripts/check-test-baseline.mjs:117-138`; `auralis-web/frontend/test-baseline.json:80`; `.github/workflows/frontend-test.yml:68-69`
- **Status**: NEW (frontend counterpart of CLOSED backend #5091)
- **Description**: `check-test-baseline.mjs` computes `fixed` (baseline entries that no longer fail) but only `console.log`s them. The only failing exit paths are for new unlisted failures, a missing report, or 0 tests. The workflow runs `pnpm run test:baseline` with no strict flag. The backend gained `check_pytest_baseline.py --strict-stale` specifically because stale entries silently re-permit the exact failure they name (#5091, 69 entries). The frontend gate never got the same protection. There is already one confirmed stale entry: `TrackRow.test.tsx::TrackRow Rendering should render drag handle if draggable` (baseline line 80). That test title no longer exists anywhere under `src/`.
- **Evidence**:
  ```js
  // check-test-baseline.mjs
  const fixed = [...baseline].filter((id) => !current.has(id)).sort();
  if (fixed.length) {
    console.log(`\n✔ ${fixed.length} baseline failure(s) no longer fail:`);
    ...                                  // no process.exit — job stays green
  }
  ```
  `grep -rn "drag handle if draggable" src` → no matches, while `test-baseline.json:80` still lists it.
- **Impact**: Once a listed test is fixed, a later regression of that same test passes CI silently. The baseline can also only accumulate cruft. The one current stale entry is harmless (the test is gone), but the mechanism that caught 69 backend cases is missing here.
- **Siblings**: A full sweep of all 108 entries against their spec files found only this one.
- **Suggested Fix**: Add a `--strict-stale` mode that exits non-zero when `fixed.length > 0`, wire it into `frontend-test.yml`, and regenerate the baseline once from a local `pnpm run test:ci`. Downloaded CI artifacts break the path matching.

### FE-03: The main library track list uses a second, unguarded pagination implementation, which defeats the #5026 guard
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/hooks/library/useLibraryPagination.ts:87-109,163-170`; compare `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts` (`QUERY_TYPE_GUARD`, `validate:`)
- **Status**: NEW
- **Description**: `useLibraryQuery.ts`'s #5026 comment says its three list fetches are "this hook's only fetch call sites, so wiring them here is the one place that covers every consumer". That is false. `useLibraryPagination.ts` independently paginates the same `/api/library/tracks` (and `/tracks/favorites`) with raw `fetch()`. It never calls `isTracksListShape`, types the body inline, and defaults a missing `tracks` key to `[]`. It is live: `CozyLibraryView` → `useLibraryWithStats` → `useLibraryPagination`.
- **Evidence**:
  ```ts
  const response = await fetch(getApiUrl(endpoint), { signal: controller.signal });
  const data: { tracks?: TrackApiResponse[]; has_more?: boolean; total?: number } = await response.json();
  const transformedTracks: LibraryTrack[] = transformTracks(data.tracks || []);
  // success toast only fires when data.tracks.length > 0
  ```
- **Impact**: If backend drift renames or drops `tracks` (the failure class #4441/#5026 exist to catch), the main library view renders empty with no error toast. Fields match today, so this is a coverage gap, not a live break.
- **Siblings**: FE-04 (same root cause on album detail). Raw-fetch timeouts on this file are already tracked in #5019.
- **Suggested Fix**: Route both fetches through `get()` in `utils/apiRequest.ts` with `validate: isTracksListShape`. Better, retire one of the two duplicate track-pagination stacks (No-variants principle) and correct the #5026 comment.

### FE-04: `useAlbumDetails` fetches album tracks as `get<any>` with no response guard
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/components/library/Details/useAlbumDetails.ts:55-87`
- **Status**: NEW
- **Description**: `GET /api/albums/{id}/tracks` is typed `any` and validated by nothing. It then reads `data.tracks`, `album_id`, `album_title`, `artist`, `year`, `genre` and `total_tracks` straight into an `Album`. No guard exists for this endpoint in `api/responseGuards.ts`, unlike comparable endpoints (artist tracks, queue, playlists). This file has already shipped three bugs caused by this untyped `data` (#4571 casing, #4643 error status, #5170 genre mapping, all closed). Each fix treated the symptom; the untyped response remains.
- **Evidence**:
  ```ts
  const data = await get<any>(`/api/albums/${albumId}/tracks`, { signal: controller.signal });
  const albumData: Album = { id: data.album_id, title: data.album_title, artist: data.artist, ..., track_count: data.total_tracks };
  ```
- **Impact**: Any backend rename on this endpoint shows up as `undefined`/`NaN` in Album Detail, with no error and no dev warning.
- **Siblings**: FE-03. No other live REST fetch in production code uses a raw `any` response type.
- **Suggested Fix**: Add an `AlbumTracksApiResponse` type in `api/transformers/types.ts` and an `isAlbumTracksResponseShape` guard in `api/responseGuards.ts`, then pass `validate:` to `get()`.

### FE-05: Backend validation (422) field errors are never shown; `httpError.ts` parses a shape this backend doesn't send, and two call sites bypass it
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/utils/httpError.ts:26-57`; `auralis-web/backend/config/app.py:87-102`; bypassing call sites `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:144-146` and `auralis-web/frontend/src/hooks/library/useLibraryScan.ts:137-139`
- **Status**: NEW
- **Description**: `httpError.ts` is the shared error-body normalizer. It formats FastAPI's *default* 422 body, a `detail` array of `{loc, msg, type}`. The backend replaces that default with a custom `RequestValidationError` handler that returns `{"detail": "Validation error", "errors": [{"field": ..., "message": ...}]}`. No frontend code reads `errors`, so `formatValidationDetail` never runs against this backend, and every 422 surfaces as the bare string "Validation error". Two call sites also skip `httpError.ts` entirely:
  - `useMetadataForm` does `const errorData = await response.json(); throw new Error(errorData.detail || ...)`.
  - `useLibraryScan` does the same inline.

  On a non-JSON error body (a plain-text 500 or a proxy error page), `response.json()` throws a `SyntaxError`. Its message ("Unexpected token ...") becomes the user-visible error: `useMetadataForm.ts:163` sets `setError(err.message)`.
- **Evidence**:
  ```py
  # backend/config/app.py
  return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": errors})
  ```
  ```ts
  // httpError.ts — only detail/message are read; `errors` never is
  return { parsed: true, detail: coerceDetail(detail) ?? coerceDetail(message) };
  // useMetadataForm.ts:144-146 — bypasses httpError
  const errorData = await response.json();
  throw new Error(errorData.detail || 'Failed to save metadata');
  ```
- **Impact**: When the metadata editor or any other form fails backend validation (for example `MetadataUpdateRequest`, `extra="forbid"`, typed `year`), the user sees "Validation error" with no field or reason. A non-JSON error body shows a JSON parse error instead of the HTTP failure. This is a backend/frontend contract mismatch (minimum MEDIUM).
- **Siblings**: Every consumer of `httpError.ts` (`apiRequest.ts`, `useRestAPI.ts` and the fingerprint/library hooks) is affected by the unread `errors` array. The two inline call sites above are additionally affected by the JSON-parse issue.
- **Suggested Fix**: Teach `readHttpErrorBody` to format the backend's `errors: [{field, message}]` shape, or align the backend handler with FastAPI's default. Replace both inline blocks with `throw await httpErrorFromResponse(response)`.

---

### LOW

### FE-06: `useProgressiveImageLoader` retry path loops forever and never clears its timer (latent — only caller disables retry)
- **Severity**: LOW
- **Dimension**: Component Quality / Hook Correctness
- **Location**: `auralis-web/frontend/src/components/shared/ui/media/useProgressiveImageLoader.ts:30-73`; only production caller `auralis-web/frontend/src/components/album/AlbumArt.tsx:127-140`
- **Status**: NEW (distinct from CLOSED #4866, the `?`/`&` cache-buster separator, which is still fixed)
- **Description**: The effect lists `retryCount` in its deps and also calls `setRetryCount(0)` unconditionally at the top of every run. On error, a bare `setTimeout` bumps `retryCount` to 1. The effect re-runs, starts loading `src?retry=1`, then resets `retryCount` to 0. That triggers another run, whose cleanup nulls the retry image's `onload`/`onerror` and reloads the plain `src`. The cycle repeats: `maxRetries` is never reached, `imageError` is never set, a retry that would have succeeded is discarded, and the skeleton shows forever with one request per second. Separately, the timer id is never stored or cleared, so it fires after unmount or `src` change. The only caller (`AlbumArt`) passes `retryOnError={false}` and `maxRetries={0}`, so none of this runs in production today. The existing spec (`useProgressiveImageLoader.test.ts`) only asserts that the `retry=1` URL appears once, so it passes despite the loop.
- **Evidence**:
  ```ts
  useEffect(() => {
    setImageLoaded(false); setImageError(false); setImageSrc(null);
    setRetryCount(0);                                   // resets the counter the retry just bumped
    ...
    img.onerror = () => { if (retryOnError && retryCount < maxRetries) {
      setTimeout(() => setRetryCount((p) => p + 1), retryDelay);   // never cleared
    } ... };
    img.src = retryCount > 0 ? `${src}${retrySeparator}retry=${retryCount}` : src;
    return () => { img.onload = null; img.onerror = null; };
  }, [src, onLoad, onError, retryCount, retryOnError, maxRetries]);
  ```
- **Impact**: None in production today. Any future `<ProgressiveImage>` that uses the default `retryOnError=true` gets an endless request loop and a permanent skeleton for any broken artwork URL.
- **Suggested Fix**: Reset `retryCount` only when `src` changes (a separate effect keyed on `src`, or a ref), store the timer and `clearTimeout` it in cleanup, and add a spec that drives two consecutive failures to the error state. Alternatively delete the retry path, since no caller uses it.

### FE-07: Redux `isLoading`/`error` on player/queue/cache slices are never dispatched; four combinator hooks are dead
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerSlice.ts:189-210`, `auralis-web/frontend/src/store/slices/queueSlice.ts:239-260`, `auralis-web/frontend/src/store/slices/cacheSlice.ts:76-97`; consumed via `auralis-web/frontend/src/hooks/shared/useReduxState.ts`
- **Status**: NEW (distinct from CLOSED #4921, which covered the reset/clear actions)
- **Description**: `setIsLoading`/`setError` exist on all three slices, but no production code imports or dispatches them. The only non-test imports of these slices are the reducers in `store/index.ts`. Real loading and error state lives in hook-local `useState` (`useQueueMutations`, `useQueueFetch`, the `hooks/api/*` hooks). `usePlayer()`, `useCache()`, `useIsLoading()` and `useAppErrors()` have no production callers and read fields that can never change. `cache.error` can be cleared but never set.
- **Impact**: None today. It is a trap: UI wired to these documented selectors would show a spinner or error banner that never appears.
- **Related**: #5239 (useReduxState.ts size), #5016/#5129 (dead selectors).
- **Suggested Fix**: Delete the unwired reducers, the selectors and the four dead hooks, or dispatch them from the hooks that own the real state. Do one, not both.

### FE-08: `StreamingInfo.intensity` is written on every `startStreaming` and read by nothing
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/playerStreamingReducers.ts:34,54,84`
- **Status**: NEW
- **Description**: The only reader of this sub-state, `usePlayEnhanced.ts:206-222`, never touches `.intensity`, and no reducer guard or component does either. The live intensity is `useEnhancementControl()` local state.
- **Impact**: None. It misleads maintainers into thinking Redux tracks per-stream intensity.
- **Suggested Fix**: Drop the field from `StreamingInfo` and from the `startStreaming` payload.

### FE-09: `usePlayerActions().setTrack` bypasses `setCurrentTrackAndSyncQueue`
- **Severity**: LOW
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:81-88`; compare `auralis-web/frontend/src/store/slices/playerQueueSync.ts:35-49`
- **Status**: NEW (same bug class as CLOSED #3587 and #4580)
- **Description**: `setTrack` dispatches the raw `setCurrentTrack` with no queue-index reconciliation. Every live call site uses the sync thunk or pairs the two dispatches itself. `setTrack` has zero production callers; the hook's only consumer, `useContextMenuActions.ts`, never calls it.
- **Impact**: None today. A future caller would bring back the `player.currentTrack` / `queue.currentIndex` desync from #3587.
- **Suggested Fix**: Delete `setTrack`, or make it dispatch `setCurrentTrackAndSyncQueue`.

### FE-10: Two exported hooks named `usePlaybackProgress` with incompatible return types
- **Severity**: LOW (downgraded from MEDIUM at merge: the colliding copy has no production callers)
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:449-453` (barrelled from `auralis-web/frontend/src/hooks/shared/index.ts:26`) vs `auralis-web/frontend/src/contexts/playbackSessionContexts.ts:87-93`
- **Status**: NEW
- **Description**: The context version, used by `Player.tsx`, returns `{processedChunks, totalChunks, currentTime}`. The `hooks/shared` version returns a bare `currentTime / duration` ratio from Redux, and only its own test uses it. Auto-import can pick either.
- **Impact**: A future consumer that imports from `@/hooks/shared` gets a number instead of the session object, either a type error or a silently wrong progress source.
- **Related**: #5239.
- **Suggested Fix**: Delete the dead Redux version (and its barrel export and test), or rename it, for example `usePlayerProgressRatio`.

### FE-11: `useAudioVisualization.ts` exports dead AudioContext/analyser wiring that duplicates `AudioPlaybackEngine`
- **Severity**: LOW
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/hooks/audio/useAudioVisualization.ts:65-96,317-332`; real implementation in `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:74-85`
- **Status**: NEW (distinct from CLOSED #4481)
- **Description**: `registerAudioContext`, `connectToVisualizer` and the local `getOrCreateAnalyser` have no production callers. The live analyser is created by `createGlobalAnalyser()` in `AudioPlaybackEngine`, which carries the #2488 stale-context guard the dead copy lacks. The hook only needs the read side (`getGlobalAudioContext()`).
- **Impact**: None today. If revived, the dead copy would bring back the #2488 `InvalidStateError` after a sample-rate change.
- **Suggested Fix**: Delete the three dead functions and their re-exports from `hooks/audio/index.ts`.

### FE-12: `types/domain.ts` exports 15 types/consts with zero importers
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/types/domain.ts:111-320`
- **Status**: NEW (distinct from CLOSED #5218 and OPEN #5234)
- **Description**: Only 10 symbols are ever imported from `@/types/domain`: `Track`, `PlayerTrack`, `QueueTrack`, `LibraryTrack`, `DetailTrack`, `TrackRef`, `Album`, `Artist`, `EnhancementPreset`, `LibraryStats`. These 15 are never imported: `Queue`, `PlayerState`, `EnhancementSettings`, `ENHANCEMENT_PRESETS`/`_NAMES`/`_DESCRIPTIONS`, `MasteringRecommendation`, `ScanProgress`, `AppState`, `ConnectionStatus`, `AppError`, `AppErrorType`, `Selection`, `FilterOptions`, `SortOptions`, `PaginationState`, `PaginatedResponse`. Several share a name with a different live type (`playerSlice.ts` `PlayerState`, `useScanProgress.ts` `ScanProgress`, `useWebSocketConnection.ts` `ConnectionStatus`).
- **Impact**: Drift risk: someone edits the dead copy and expects an effect.
- **Suggested Fix**: Delete them, keeping the live same-named types as the single source.

### FE-13: `createEndpointGenerator` in `serviceFactory.ts` is dead and typed entirely with `any`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/utils/serviceFactory.ts:237-248`
- **Status**: NEW
- **Description**: `withId(id: any)`, `withParam(key, value: any)` and `withParams(params: Record<string, any>)` are referenced only by `utils/__tests__/serviceFactory.test.ts`. Real endpoints are hand-typed in `config/api.ts`. Note: this file has uncommitted user edits (the #5123 guard work), which do not touch this function.
- **Suggested Fix**: Delete the function and its test (after the in-progress edit lands, to avoid conflicts).

### FE-14: Scattered low-impact `any`
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts:93,102-103,160` (dev-only); `auralis-web/frontend/src/hooks/app/keyboardShortcutDefinitions.ts:21`; `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:118,121`
- **Status**: NEW
- **Description**: The logger middleware's `any[]` / `Record<string, any>` only runs in DEV. Handler args are typed `any[]`. The PATCH-payload builder casts to `Record<string, any>`. None of these has behavioural consequences.
- **Suggested Fix**: Use `unknown[]` / `Record<string, unknown>`, and type `updates` per key.

### FE-15: Literal spacing and font-size values duplicate existing tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/ArtistListLoading.tsx:21,24`, `auralis-web/frontend/src/components/library/Items/albums/AlbumGridLoadingState.tsx:28`, `auralis-web/frontend/src/components/playlist/DroppablePlaylist.styles.ts:11`, `auralis-web/frontend/src/components/library/Styles/Typography.styles.ts:41`, `auralis-web/frontend/src/components/library/Items/tracks/TrackRow.styles.ts:147`, `auralis-web/frontend/src/components/shared/DropZone/DropZoneText.tsx:59`
- **Status**: NEW
- **Description**: `'20px'`, `'12px'`, `'8px'` and `'2px'` spacing strings, plus `fontSize: 11`, each exactly equal an existing token (`tokens.spacing.lg/md/cluster/xxs`, `tokens.typography.fontSize.xs`). 106 other component files already use the tokens. The import-path check found no relative `../` imports in production code, and no hardcoded mode-dependent colours (#4877 is still fixed).
- **Impact**: These values won't follow a future change to the tokens.
- **Suggested Fix**: Replace them with the matching tokens.

### FE-16: MUI numeric `sx` spacing is a second spacing scale that doesn't come from the tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts` (`createTheme` has no `spacing`); 19 consumers, including `auralis-web/frontend/src/components/shared/DropZone/DropZoneIcon.tsx`, `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx`, `auralis-web/frontend/src/components/settings/SettingsDialog.tsx` and the four `auralis-web/frontend/src/components/shared/ui/loaders/*Skeleton.tsx`
- **Status**: NEW
- **Description**: `p: 2`, `mb: 3` and similar resolve through MUI's default 8px grid, which has no link to `tokens.spacing` (2/4/6/12/20/28px…). For example, `mb: 2` = 16px has no token equivalent.
- **Suggested Fix**: Configure `createTheme({ spacing })` from the tokens, or migrate the 19 files to `tokens.spacing.*`.

### FE-17: API retry is not status-aware, and the only backoff implementation is dead
- **Severity**: LOW (merged from two MEDIUM dimension findings; the orchestrator downgraded them because the desktop app talks to localhost and errors still surface)
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/App.tsx:15-23` (`retry: 1`); `auralis-web/frontend/src/utils/errorHandling.ts:1-13,83-122,354-364`; `auralis-web/frontend/src/utils/apiRequest.ts`
- **Status**: NEW. The dimension agent tagged this "Regression of #4442". That was rejected: #4442 was closed for its timeout half, and its proposal only said to "consider bounded retry".
- **Description**: The global `QueryClient` retries every query once, even on a 404, a 400 or a guard failure. Only the fingerprint hooks opt out. `isRetryableError`, `retryWithBackoff` and `DEFAULT_RETRY_POLICY` in `errorHandling.ts` encode the correct rule (0/408/429/5xx), but the file's own header says "no current consumers". Neither `apiRequest.ts` nor `useRestAPI.ts` retries.
- **Impact**: An extra round trip before a permanent error shows. A transient 503 or 429 is never retried outside React Query.
- **Related**: #5198, #5019, #5190.
- **Suggested Fix**: Use `retry: (n, e) => n < 1 && isRetryableError(e)` in `App.tsx`. Either wire the backoff into `apiRequest` for idempotent GETs or delete the dead module.

### FE-18: `ArtistListItem` is the only virtualized row component without `React.memo`
- **Severity**: LOW (downgraded from MEDIUM at merge: bounded to about 20 visible rows re-rendering, no measurable jank)
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/artists/ArtistListItem.tsx:25-66`; `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx:106-109`
- **Status**: NEW
- **Description**: `SelectableTrackRow`, `QueueTrackItem`, `AlbumCard`, `TrackTableRowItem` and `ArtistTrackRow` are all memoized (#4177, #3929, #4472). `ArtistListItem` is not, even though `ArtistListContent.tsx:78` carries a #3607 comment stabilizing callbacks "so ArtistListItem doesn't re-render needlessly". `CozyArtistList` also passes an inline `onContextMenuClose` closure. Opening or closing the context menu re-renders every mounted row (viewport plus `overscan: 8`).
- **Suggested Fix**: Wrap `ArtistListItem` in `memo` and give `onContextMenuClose` a `useCallback`.

### FE-19: Album and Artist Detail views render no `<h1>`
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/Details/DetailViewHeader.tsx:132-138`
- **Status**: NEW (sibling of CLOSED #4958 and #5013, whose fix and test cover only `ViewContainer`)
- **Description**: `h1` is rendered only in `ViewContainer.tsx:65`, `LibraryHeader.tsx:24` and the `ErrorBoundary` fallback. The detail views use `DetailViewHeader`, whose title is `variant="h2"` (it renders an `<h2>`), followed by an `h5` subtitle. `singleH1PerView.test.tsx` tests only `AppTopBar` plus `ViewContainer`.
- **Impact**: Heading-level navigation finds no level-1 heading on two primary views, and the levels skip from h2 to h5.
- **Suggested Fix**: Add `component="h1"` to the title (keep the visual variant) and make the subtitle an `h2`. Extend the single-h1 spec to cover the detail views.

### FE-20: `ClearQueueDialog` builds its own focus trap instead of using `useDialogAccessibility`
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/player/QueuePanel/ClearQueueDialog.tsx:1-60`
- **Status**: NEW
- **Description**: The file has its own Tab wrap, Escape handling, focusable-element query and focus restore. It works correctly, but it duplicates `focusManager.createFocusTrap` (in `a11y/focusManagement.ts`), which `ConfirmationDialog` and `QueueSearchPanel` use through `useDialogAccessibility`.
- **Impact**: Two copies of accessibility-sensitive logic that can drift apart.
- **Suggested Fix**: Switch to `useDialogAccessibility(onCancel)`.

### FE-21: `AppMainContent` declares `onPlayTrack`/`onQueueTrack` props that are never used
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/core/AppMainContent.tsx:16-27,62-66`
- **Status**: NEW
- **Description**: The props are destructured to `_onPlayTrack`/`_onQueueTrack` and discarded, and the only call site (`ComfortableApp.tsx`) doesn't pass them. The JSDoc and `@example` imply they work.
- **Suggested Fix**: Delete the props and the stale JSDoc.

### FE-22: EditMetadataDialog and SimilarTracksModal unmount in the same render that closes them, so the exit transition never plays
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/CozyLibraryView.tsx:263-286`; `auralis-web/frontend/src/components/library/useMetadataEditing.ts:15-18`; `auralis-web/frontend/src/components/library/useSimilarTracksModal.ts:26-30`
- **Status**: NEW
- **Description**: Each dialog's mount is gated by `editingTrackId` / `similarTracksModalOpen`, and the close handler clears that gate in the same batch that sets `open=false`. The MUI Dialog is removed before its fade-out runs, so both dialogs close with a hard cut.
- **Suggested Fix**: Gate mounting on "has been opened" (or clear the gate in `TransitionProps.onExited`). Keep the lazy loading from #3956.

### FE-23: The transport logic in `PlaybackSessionContext` (previous, mute toggle, auto-advance) has no direct tests
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx:141-161,199-210,216-232`
- **Status**: NEW
- **Description**: `handleNext` has dedicated tests through `Player.test.tsx` (#4410, #4812, #4835). `handlePrevious`, `handleMuteToggle` (volume save/restore and 0-1 ↔ 0-100 conversion) and the auto-advance effect (guarded by `hasAutoAdvancedRef`) are never run under test. `PlaybackControls.test.tsx` and `VolumeControl.test.tsx` only check that prop callbacks fire. `PlaybackSessionContext.split.test.tsx` covers only re-render isolation (#5006).
- **Impact**: A coverage gap only; there is no evidence of breakage. These are the same kinds of races and desyncs this file was written to prevent.
- **Suggested Fix**: Mirror the Next tests for Previous, add a mute round-trip test, and drive `streamingState: 'complete'` near the track's end to assert that auto-advance fires exactly once.

---

## Dropped at Merge (false positives or already tracked)

| Dimension claim | Disposition |
|---|---|
| D8: FoldersList "Remove this folder" button has no accessible name (tagged "Regression of #4473") | **False positive.** MUI 9.0.1 `Tooltip` defaults to `describeChild=false` and copies a string `title` into the child's `aria-label` (`Tooltip.js:473-479`), so the button is named "Remove this folder". #4473 was a house-style request, not a missing name. |
| D8: StyledDialog-based dialogs (Settings, Create/Edit Playlist, ArtistInfo, KeyboardShortcutsHelp, SimilarTracks, remove-folder confirm) lack an accessible name | **False positive.** MUI 9 `Dialog` always generates `aria-labelledby` (via `useId`) and passes it through `DialogContext`. `DialogTitle` uses it as its `id` (`Dialog.js:272-307`, `DialogTitle.js:49-57`). Each flagged dialog renders `DialogTitle` or `StyledDialogTitle` (a styled `DialogTitle`). |
| D3: `KEYBOARD_SHORTCUTS` in `useKeyboardShortcuts.ts:146-150` still lists Gentle/Warm/Bright/Punchy presets | Confirmed, but it is part of the dead V1 surface that OPEN **#5231** already proposes deleting. Add a comment on #5231 noting it also carries four removed presets. No new issue. |

## Existing Issues Re-verified

- **#5102** (EditMetadataDialog has no accessible name): **still valid**. Unlike the dialogs above, its header uses `DialogTitleStyled = styled(Box)` (`EditMetadataDialog.styles.ts:11`), not `DialogTitle`, so MUI's auto `aria-labelledby` points at an id that doesn't exist.
- **#5134** (design-system Modal close button): **moot, can be closed**. The design-system Modal primitive was deleted in `1602e500` (#5216/#5217).
- **#5123** (createCrudService write responses unvalidated): **partially fixed in the uncommitted working tree**. `serviceFactory.ts` now accepts `create`/`update`/`delete`/`custom` guards, and `settingsService.ts` wires `isSettingsResponse` for `reset`, `addScanFolder`, `removeScanFolder` and `updateSettings`. That matches the backend `SettingsUpdateResponse` and `_ScanFolderRequest.folder`. `playlistService.ts` (list/get guards only) and `queueService.ts` (list only) still have unguarded writes, so #5123 should stay open after that edit lands.
- Still open and still accurate: #5009, #5011, #5016, #5018, #5019, #5101, #5129, #5131, #5132, #5163 (the method is already gone; close as moot), #5186/#5179, #5189, #5190, #5198, #5234, #5239, #4820.
- Closed and confirmed still fixed: #3924 (rules of hooks), #4428/#4177 (queue keys/memo), #4866, #4880, #4877, #3945, #4584, #4921, #5218, #4446, #3928, #3929, #4472, #5006, #4632, #4176, #4147, #4869, #5120, #4471, #4491, #4541.

## Relationships

- **Guard coverage gaps (FE-03, FE-04, #5123, #5009).** All four share one root cause: runtime response validation is opt-in per call site, and the call sites that predate `responseGuards.ts` were never migrated. FE-03 is the most serious instance because its failure mode is silent (an empty main library). Retiring the duplicate pagination stack (FE-03) also removes one of the raw-fetch call sites tracked in #5019.
- **Error normalization (FE-05, FE-17).** Both are about `httpError.ts` / `apiRequest.ts` being "the single transport" only on paper: a mismatched 422 contract, inline bypasses, and no status-aware retry. Fix them together in the transport layer.
- **Dead parallel state in `useReduxState.ts` (FE-07, FE-09, FE-10, #5239, #5016, #5129).** Splitting or pruning the god-file (#5239) is the natural place to delete the unwired `isLoading`/`error` fields, `setTrack` and the duplicate `usePlaybackProgress` in one change.
- **Hidden-until-hover controls (FE-01).** `TrackTableRowItem` and the `SelectableTrackRow` checkbox already show the correct pattern. Only `TrackRow.styles.ts` missed it, the same "fixed in one sibling, not the other" shape as FE-18 (memo) and FE-19 (h1).
- **CI honesty (FE-02).** This is the frontend sibling of the backend #5091/#5095 work. Pair it with a baseline regeneration once FE-01, FE-06 and FE-23 add or fix tests.

## Prioritized Fix Order

1. **FE-01**: two CSS rules. Restores WCAG 2.4.7 on the busiest view and needs no design decision.
2. **FE-03**: removes the silent empty-library failure mode on the main view. Ideally retire one pagination stack, which also shrinks #5019.
3. **FE-05**: fix the shared parser for the backend's `errors` shape and route the two inline sites through `httpErrorFromResponse`, so validation errors become readable everywhere.
4. **FE-02**: add `--strict-stale` to the frontend gate before more fixes land, so fixed tests can't silently regress. Regenerate the baseline once to drop the stale TrackRow entry.
5. **FE-04**: add a guard for album tracks (the same pattern as FE-03, a small change).
6. **FE-17, FE-06**: transport retry policy, and the latent image-retry loop (fix it or delete the retry path before anyone enables it).
7. **Dead-surface cleanup batch** (FE-07 to FE-13, FE-21), done together with #5239 / #5231 / #5129.
8. **Polish**: FE-18, FE-19, FE-20, FE-22, FE-15, FE-16, FE-14, FE-23.
