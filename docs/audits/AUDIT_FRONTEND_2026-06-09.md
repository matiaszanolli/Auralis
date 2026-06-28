# Frontend Audit — Auralis React Frontend

**Date**: 2026-06-09
**Scope**: `auralis-web/frontend/src/` — components, Redux store, hooks, services, design system, TypeScript, accessibility, tests
**Depth**: deep (full call-graph / dispatch-flow tracing) · **Limit**: unlimited · **Dimensions**: all 9
**Method**: 9 parallel dimension agents (general-purpose / sonnet, max 3 concurrent), findings cross-deduplicated and the highest-severity claims re-verified by the orchestrator against live code.

> **Dedup note**: GitHub API was unreachable during this audit (`gh issue list` failed — no network). The dedup baseline was reconstructed from the two most recent frontend audit reports (2026-05-29, 2026-05-26), older reports, and 700+ local `.claude/issues/` snapshots. Issue numbers cited as `#NNNN` come from those local snapshots; verify state at publish time once GitHub is reachable.

---

## Executive Summary

**69 NEW findings** after cross-dimension deduplication: **2 CRITICAL, 8 HIGH, 34 MEDIUM, 25 LOW**. In addition, the frontend has churned heavily since the 2026-05-29 audit (design-token split #4079, `index.css`↔token reconciliation #3927, WS-type split #4081, `useLibraryWithStats` decomposition, artist/album virtualization, dead-code deletion) — **a large number of prior findings were verified FIXED** and are listed per dimension below.

### Findings by severity

| Severity | Count | Headline findings |
|----------|-------|-------------------|
| CRITICAL | 2 | Rules-of-Hooks violation in `RecentlyTouchedSection`; 43 production `tsc` errors with **no CI type-check gate** |
| HIGH | 8 | 4 player-state WS messages have **zero Redux subscribers**; `serviceFactory.custom()` type hole breaks settings-save; `FingerprintProgress` `'cached'`/`'queued'` dropped; 100 MB PCM buffer never `dispose()`d; `QueueSearchPanel` has no focus trap; 3 critical-path test suites broken/missing |
| MEDIUM | 34 | post-unmount setState clusters, NaN/unvalidated WS dispatches, off-palette logo/gradient colors, missing `aria-label`s, contract drift, latent `useLibraryQuery` refetch loop |
| LOW | 25 | size-rule violations, token-bypass rgba literals, dead selectors, minor a11y gaps |

### Key themes

1. **Type-safety is silently eroding** — the single most important finding. `tsc --noEmit` produces **371 errors (43 in production source)**, but no CI step runs it, so every PR can add type holes invisibly. Several of those 43 are genuine runtime bugs (settings-save crash, dropped fingerprint statuses, queue-track `filepath` undefined). *Verified by the orchestrator.*
2. **WebSocket → Redux contract drift** — four player-state event messages (`playback_paused/stopped`, `track_changed`, `volume_changed`) are documented in code comments as "updates the Redux player slice" but have **no subscriber anywhere**. State stays eventually-consistent only via the periodic `player_state` snapshot. *Verified: 0 subscribers.*
3. **Post-unmount setState is the most common hook/component defect** — at least 6 distinct sites (`PlaylistList`, `useEnhancementParameters`, `usePlayTrack`, `useSimilarTracks`, `usePaginatedAPI` pagination callbacks, `saveMetadata`) fetch without wiring an `AbortController`/`mountedRef` to cleanup. The same fix pattern (`toastRef`/`mountedRef`/`controller.abort()` in cleanup) applies to all.
4. **Rules-of-Hooks regression** — `RecentlyTouchedSection` re-introduces the exact bug class fixed in `LibraryViewRouter` (#3924): a hook called after an early `return null`.
5. **Test rot on critical paths** — broken mocks make several suites assert against unreachable/renamed code (`useEnhancementControl` 5/28, `enhancement-pane` 11/20, `usePlayEnhanced` 20/47), and the new `usePlayTrack` "play this track" entry point has zero tests.
6. **Design-token discipline is strong but leaky at the edges** — the #4079/#3927 refactors are clean; remaining drift is concentrated in the SVG logo, three `index.css` aurora-gradient variables, and the `--space-*` scale that #3927 never reconciled.

### Most impactful (recommended single-PR fixes)

- **Add `tsc --noEmit` to CI and fix the 43 production errors** (TS-NEW-1 + root causes TS-NEW-2/3/6/7) — closes a whole class of silent regressions and 2 real runtime bugs.
- **Move `useAlbumFingerprints` above the early return in `RecentlyTouchedSection`** (FE-D1-1) — one-line fix for a CRITICAL crash.
- **Add a `usePlayerEventSync` subscriber for the 4 unhandled WS events** (RS-NEW-1) — removes player-state divergence on pause/stop/skip/volume.

---

## Verification Notes (orchestrator)

The following high-stakes claims were independently re-verified against live code before inclusion:

| Claim | Verdict | Evidence |
|-------|---------|----------|
| TS-NEW-1: 43 production tsc errors, no CI gate | **CONFIRMED** | `npx tsc --noEmit` → 371 total, 43 non-test; `.github/workflows/` has only `build-release.yml`, no `type-check` step |
| FE-D1-1: hook after early return | **CONFIRMED** | `RecentlyTouchedSection.tsx:43` `return null` precedes `useAlbumFingerprints` at `:51` |
| RS-NEW-1: 4 WS messages unsubscribed | **CONFIRMED** | grep across `src/` → 0 `subscribe()`/`useWebSocketSubscription` for all four types |
| PF-NEW-2: PCM buffer not disposed | **CONFIRMED** | `PCMStreamBuffer.dispose()` exists; `usePlayEnhanced.ts:258,596` null the ref without calling it |
| HC-NEW-6 TDZ: `clearTimeout(timeout)` before `const timeout` | **CONFIRMED → downgraded to MEDIUM** | `useMasteringRecommendation.ts:75` references `timeout` declared at `:90`; production WS is async (no prod crash), fires only under synchronous delivery/tests |
| FE-D3-1 "infinite refetch loop" (HIGH) vs HC-NEW-7 (MEDIUM) | **Mechanism CONFIRMED, blast-radius CORRECTED → MEDIUM (latent)** | `useRestAPI` returns `useMemo(…, [stableMethods, isLoading, error])` so `api` churns; but the only consumers of the buggy `useLibraryQuery`/`useTracksQuery`/`useAlbumsQuery` are `TrackList` (mounted **only in a test**) and the **dead** `AlbumGrid.tsx`. Active views use `useInfiniteAlbums` (React Query) + `useLibraryPagination`. Not live in production. |
| AlbumGrid.tsx dead | **CONFIRMED** | `LibraryViewRouter.tsx:17,193` imports/renders `CozyAlbumGrid`, not `AlbumGrid` |

---

## CRITICAL Findings

### CRIT-1 (FE-D1-1): `RecentlyTouchedSection` calls a hook after an early `return null` — Rules of Hooks violation
- **Severity**: CRITICAL
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/RecentlyTouchedSection.tsx:42-51`
- **Status**: NEW · **Verified**
- **Description**: The component returns `null` at line 43 when `recentAlbums.length === 0`, then calls `useAlbumFingerprints(albumIds)` at line 51. The number of hooks invoked therefore differs between the empty and non-empty render. When the recently-touched list transitions from empty → non-empty (the normal case as recents populate), React throws *"Rendered more hooks than during the previous render"*, crashing the Albums view subtree.
- **Evidence**:
  ```tsx
  if (recentAlbums.length === 0) return null;          // :43 early return
  const displayedAlbums = recentAlbums.slice(0, 8);
  const albumIds = displayedAlbums.map(a => a.albumId);
  const { fingerprints } = useAlbumFingerprints(albumIds);  // :51 hook AFTER return
  ```
- **Impact**: Hard crash of the Albums view on list transition (caught only if an error boundary wraps it). Same bug class as the already-fixed `LibraryViewRouter` (#3924).
- **Suggested Fix**: Move `useAlbumFingerprints(albumIds)` above the `return null`, computing `albumIds` from the (possibly empty) list first; guard *after* all hooks.

### CRIT-2 (TS-NEW-1): 43 production `tsc` errors ship undetected — CI has no type-check gate
- **Severity**: CRITICAL
- **Dimension**: Type Safety
- **Location**: 18 production files (see table); CI config `auralis-web/frontend/package.json` (`type-check` script exists but is unused), `.github/workflows/build-release.yml`
- **Status**: NEW · **Verified** (`npx tsc --noEmit` → 371 total / 43 non-test)
- **Description**: `tsconfig.json` sets `"strict": true`, yet no CI job runs `tsc --noEmit`, so the codebase has accumulated 43 production type errors (plus 328 in tests). Reviewers never see them. Several are real runtime bugs (see HIGH-2, HIGH-3, MED-TS-6, MED-TS-7).
- **Evidence** (production error distribution):
  | File | Errors | Root cause |
  |------|--------|-----------|
  | `services/similarityService.ts` | 16 | `serviceFactory.custom()` returns `Promise<unknown>` (→ HIGH-2) |
  | `services/settingsService.ts` | 4 | same |
  | `services/artworkService.ts` | 4 | same + `ArtworkRequest` constraint |
  | `components/enhancement/EnhancementPane.tsx` | 2 | FingerprintStatus literal mismatch (→ HIGH-3) |
  | `components/settings/useSettingsDialog.ts` | 2 | `.settings` on `UserSettings` direct return (→ HIGH-2) |
  | `components/player/ProgressBar.tsx` | 2 | — |
  | `utils/errorHandling.ts` | 2 | `Cannot find namespace 'NodeJS'` |
  | `Queue{Panel,RecommendationsPanel,SearchPanel,StatisticsPanel}` | 4 | `(Track \| QueueTrack)[]` vs `Track[]` (→ MED-TS-7) |
  | `CacheManagementPanel` | 1 | `track_id` number/string (→ MED-TS-6) |
  | `types/ws/registry.ts`, `SearchBar.tsx`, `ConnectionStatusIndicator.tsx`, `usePlayerControls.ts`, `queueService.ts`, `playlistService.ts` | 1 each | misc |
- **Impact**: A whole class of contract violations is invisible at review time and can grow unbounded; two of the clusters are live runtime bugs.
- **Suggested Fix**: Add a required CI step `npm run type-check` (exit-on-error). Fix the 43 errors — most collapse into the three root causes in HIGH-2, HIGH-3, MED-TS-6/7.

---

## HIGH Findings

### HIGH-1 (RS-NEW-1): `playback_paused`, `playback_stopped`, `track_changed`, `volume_changed` have no Redux subscriber
- **Severity**: HIGH · **Dimension**: Redux State · **Status**: NEW · **Verified** (0 subscribers)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:183,205,259,280,308`
- **Description**: Code comments claim these four WS messages "update the Redux player slice", but no `subscribe()`/`useWebSocketSubscription` handler exists for any of them. The only player-state sync path is the periodic full `player_state` snapshot in `usePlayerStateSync`. So `pause()`/`stop()` optimistic updates are never backend-confirmed, and `track_changed` after `next()`/`previous()` is dropped — `currentTrack` diverges from real playback until the next snapshot.
- **Impact**: Store holds stale `isPlaying`/`currentTrack`/queue while audio continues; divergence window grows under rapid skips. `playback_started`/`playback_resumed` are likewise defined and unsubscribed.
- **Suggested Fix**: Add a `usePlayerEventSync` subscriber mapping `playback_paused→setIsPlaying(false)`, `playback_stopped→resetPlayer()`, `volume_changed→setVolume`, `track_changed→setCurrentIndex(track_index)`.

### HIGH-2 (TS-NEW-2): `serviceFactory.custom()` returns `Promise<unknown>` — 15 compile errors + settings-save runtime crash
- **Severity**: HIGH · **Dimension**: Type Safety · **Status**: NEW · **Verified** (part of the 43)
- **Location**: `auralis-web/frontend/src/utils/serviceFactory.ts:121`; `services/similarityService.ts:93-164` (9 fns); `services/settingsService.ts:117-132` (3 fns); `services/artworkService.ts:26,37-52` (3 fns); consumer `components/settings/useSettingsDialog.ts:66`
- **Description**: `custom()` is typed `Promise<unknown>` but 15 service functions return it directly from functions declaring concrete interfaces, yielding 15 TS2322 errors. Worse, `useSettingsDialog` reads `result.settings` on the return of `updateSettings()`, which resolves to `UserSettings` directly (no `.settings` wrapper) → `undefined` at runtime, so the settings panel fails to save on first attempt.
- **Suggested Fix**: Add a generic `custom<R = unknown>()` and supply the expected type at each call site (or call `get`/`post` from `apiRequest.ts` with explicit generics). Fix `useSettingsDialog` to use the actual `UserSettings` shape.

### HIGH-3 (TS-NEW-3): `FingerprintProgress` `'cached'`/`'queued'` statuses dropped by Enhancement components
- **Severity**: HIGH · **Dimension**: Type Safety · **Status**: NEW · **Verified** (2 of the 43)
- **Location**: source of truth `types/ws/enhancement.ts:27`; narrow types `components/enhancement/EnhancementIdentityLayer.tsx:21`, `EnhancementInspectionLayer/types.ts:6`; errors at `EnhancementPane.tsx:151,179`
- **Description**: The backend emits `fingerprint_progress.status` ∈ {analyzing, complete, failed, error, **cached**, **queued**}. Both Enhancement UI components narrow the prop to 5 values, omitting `'cached'`/`'queued'` → two TS2322 errors. `'cached'` is the **common path** for previously-analysed tracks, which then render *no* fingerprint status indicator.
- **Suggested Fix**: Export one `FingerprintStatusType` from `types/ws/enhancement.ts`; import it in both components and add `'cached'` (check icon) / `'queued'` (spinner) handling.

### HIGH-4 (PF-NEW-2): 100 MB `PCMStreamBuffer` `Float32Array` never `dispose()`d on track switch
- **Severity**: HIGH · **Dimension**: Performance · **Status**: NEW · **Verified**
- **Location**: `services/audio/PCMStreamBuffer.ts:58,79,238` · `hooks/enhancement/usePlayEnhanced.ts:258,596`
- **Description**: `PCMStreamBuffer` allocates a `Float32Array` (default capacity 100 MB) on `initialize()`. `dispose()` exists and nulls the backing buffer, but `cleanupStreaming` and the disconnect path set `pcmBufferRef.current = null` *without* calling `.dispose()` first, leaving reclamation to GC timing. Rapid track switching can transiently hold several 100 MB dead arrays before a GC cycle.
- **Impact**: Memory pressure / potential GC-pause audio dropouts on constrained Electron hardware. (Bounded by eventual GC, hence HIGH not CRITICAL.)
- **Suggested Fix**: Call `pcmBufferRef.current?.dispose()` before nulling in `cleanupStreaming` and the unmount-cleanup effect.

### HIGH-5 (A11Y-NEW-2): `QueueSearchPanel` declares `aria-modal` but has no Tab focus trap
- **Severity**: HIGH · **Dimension**: Accessibility · **Status**: NEW
- **Location**: `components/player/QueueSearchPanel/QueueSearchPanel.tsx:76-215`
- **Description**: The panel sets `role="dialog"`/`aria-modal="true"` and focuses the search input on open, but never traps Tab — keyboard focus escapes to the background page while the modal claims to be modal (WCAG 2.4.3). `ClearQueueDialog`/`ConfirmationDialog` already implement traps via `useDialogAccessibility`.
- **Suggested Fix**: Apply the existing `useDialogAccessibility(onClose)` hook to the panel's inner `div`.

### HIGH-6 (TC-NEW-11): `useEnhancementControl` test suite — 5/28 fail against stale `post()` call shape
- **Severity**: HIGH · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `hooks/enhancement/__tests__/useEnhancementControl.test.ts:160-164,287-291,384-390,415-420,443-449`
- **Description**: Implementation now calls `post(url, { enabled })` (2-arg) but tests assert the old `post(url, undefined, { enabled })` (3-arg) shape. The 5 toggle/preset/intensity tests permanently fail and no longer exercise the real calling convention, so a regression to the 3-arg form would go undetected.
- **Suggested Fix**: Update the 5 assertions to the 2-arg form; rerun the suite.

### HIGH-7 (TC-NEW-12): `enhancement-pane` integration suite — 11/20 fail against renamed component API
- **Severity**: HIGH · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `tests/integration/enhancement-processing/enhancement-pane.test.tsx:269,336,359,377,406,420,445,469,499,523,538`
- **Description**: Tests query `getByRole('button', { name: /disable|enable/i })`, but after the Identity/Inspection-Layer refactor no such accessible name exists (`EnhancementToggle` has no enable/disable `aria-label`). 11/20 throw `Unable to find … button … /disable|enable/i`; the entire enable/disable + optimistic-update/rollback path is untested at integration level. **Related to A11Y gap** — adding the `aria-label` (see MED-A11Y group / TC-NEW-12 fix (a)) fixes both.
- **Suggested Fix**: Add `aria-label={enabled ? 'Disable enhancement' : 'Enable enhancement'}` to the toggle (also improves a11y), or query by the real accessible name.

### HIGH-8 (TC-NEW-15): `usePlayTrack` — the sole "play this track" entry point has zero tests
- **Severity**: HIGH · **Dimension**: Test Coverage · **Status**: NEW
- **Location**: `hooks/player/usePlayTrack.ts:1-70`
- **Description**: `usePlayTrack` (introduced to replace `onTrackPlay` prop drilling, CQ-4 / #3940) combines a REST queue POST and a WS `play_enhanced` send, gated by a critical `if (!queueResponse.ok) throw` guard that prevents a "ghost stream" when the queue update fails. It has no tests, so removing that guard would not be caught. **Related to HC-NEW-4** (this hook also lacks an `AbortController`).
- **Suggested Fix**: Add `usePlayTrack.test.ts`: success → fetch then send; failed queue POST → no send + error toast; correct `track_id`/`preset`/`intensity` payload.

---

## MEDIUM Findings

> Full evidence/snippets for each are in the per-dimension working notes; condensed here with location, status, and fix direction. All are NEW unless marked.

### Component Quality
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-CQ-1 (FE-D1-2) | `components/library/MetadataEditorDialog.tsx` (310 L) | **Dead code** + missing dialog ARIA/focus-trap. Unreferenced; replaced by `EditMetadataDialog`. **Deleting it also resolves A11Y existing-#A11Y-1.** | Delete the file. |
| MED-CQ-2 (FE-D1-3) | `components/library/AlbumGrid.tsx` (319 L) | **Dead code** (verified: `LibraryViewRouter` renders `CozyAlbumGrid`). Also the only live consumer of the buggy `useAlbumsQuery`. | Delete the file. |
| MED-CQ-3 (FE-D1-4) | `CozyLibraryView`→`LibraryViewRouter`→`ArtistDetailView`→`ArtistDetailTabs`→`AlbumTrackTable` | `currentTrackId` prop-drills through 3 pass-through components (limit is 2). | Read `selectCurrentTrack` directly in `AlbumTrackTable`. |
| MED-CQ-4 (FE-D1-5) | `player/QueueRecommendationsPanel/QueueRecommendationsPanel.tsx:92-158` | `activeTab='similar'` not reset when `currentTrack→null`; tab button unmounts but `aria-labelledby` still points at it; stale "Similar to Current" content. | `useEffect` resetting `activeTab` to `'for-you'` when `currentTrack` is null. |
| MED-CQ-5 (FE-D1-10) | `components/playlist/PlaylistList.tsx:77-128` | 4 post-`await` `setPlaylists()` paths (incl. WS callbacks) with no `isMountedRef`. | Add `isMountedRef` guard (pattern from `CacheManagementPanel`). |
| MED-CQ-6 (FE-D1-11) | `components/enhancement-pane/hooks/useEnhancementParameters.ts:62-99` | `AbortController` created but `useEffect` never returns `() => controller.abort()`; `setParams`/`setIsAnalyzing` run post-unmount (fires every track change). | Return abort from effect; check `signal.aborted` before setState. |

### Redux State
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-RS-1 (RS-NEW-2) | `hooks/player/usePlayerStateSync.ts:96,100,104` | `typeof x === 'number'` admits `NaN` for `duration`/`current_time`/`volume`; one bad message permanently `NaN`s all progress/time UI. The `position_changed` path already uses `Number.isFinite`. | Use `Number.isFinite` on all three (match `position_changed`). |
| MED-RS-2 (RS-NEW-3) | `usePlayerStateSync.ts:138`, `usePlaybackQueue.ts:230,256` | `repeat_mode` dispatched without allowlist; invalid value (e.g. `'none'`) silently halts `nextTrack`/`previousTrack`. `current_preset` already validates via `VALID_PRESETS`. | Add `VALID_REPEAT_MODES` allowlist at all 3 sites. |

### Hook Correctness
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-HC-1 (HC-NEW-2) | `hooks/app/useKeyboardShortcuts.ts:220-229` | `keyboardShortcuts.register()` called in render body (side effect in render) → double-registers in StrictMode/Concurrent. | Move into `useLayoutEffect` keyed on a serialized shortcut signature. |
| MED-HC-2 (HC-NEW-4) | `hooks/player/usePlayTrack.ts:35-58` | Queue POST has no `AbortController`; on unmount mid-request, `play_enhanced` fires + success toast on dead tree. **Related HIGH-8.** | Abort on unmount; check `signal.aborted` before `send()`/toast. |
| MED-HC-3 (HC-NEW-9) | `hooks/fingerprint/useSimilarTracks.ts:100-248` | No unmount `useEffect` aborting `abortRef`; modal dismiss mid-search leaves backend running and `loading` stuck on remount. | `useEffect(() => () => abortRef.current?.abort(), [])`. |
| MED-HC-4 (HC-NEW-6 / FE-D3-3) | `hooks/enhancement/useMasteringRecommendation.ts:75,90` | **Verified TDZ**: `clearTimeout(timeout)` (handler, :75) references `const timeout` declared at :90 after `subscribe()`. No prod crash (async WS) but deterministic `ReferenceError` under synchronous delivery / sync-mock tests. *Downgraded from agent's HIGH.* | Hoist `timeout` to a `useRef`. |
| MED-HC-5 (HC-NEW-7 / FE-D3-1) | `hooks/library/useLibraryQuery.ts:250-371` + `hooks/api/useRestAPI.ts:344` | **Verified latent**: `executeQuery` deps on whole `api` object, which churns when `useRestAPI.isLoading` flips; auto-fetch effect re-fires after each completion and the dedup guard (`isFetchingRef`) only blocks *in-flight* → would infinite-loop. **Not live**: only consumers are `TrackList` (test-only mount) + dead `AlbumGrid`; active views use `useInfiniteAlbums`/`useLibraryPagination`. *Reconciled from contradictory HIGH/MEDIUM agent reports.* | Depend on `api.get` (stable) not the wrapper object; or delete the unused `useLibraryQuery` path. |
| MED-HC-6 (FE-D3-2) | `useMasteringRecommendation.ts:54-102` | Effect cleanup on `trackId` change doesn't `setRecommendation(null)`; previous track's mastering profile stays visible up to 10 s on each skip → user may apply wrong-track preset. | `setRecommendation(null)` at effect start (after cache-hit return). |

### Type Safety
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-TS-3 (TS-NEW-4) | `types/domain.ts:194`, `types/ws/enhancement.ts:32`, +2 local defs | `MasteringRecommendationData` defined 4×; `domain.ts` marks `weighted_profiles` **required** → `TypeError` iterating it for non-hybrid profiles; hook uses `id/name` vs canonical `profile_id/profile_name`. | Single canonical type from `types/ws/enhancement.ts`; delete local defs. |
| MED-TS-4 (TS-NEW-5) | `types/ws/registry.ts:106,148`, `contexts/WebSocketContext.tsx:315` | `'audio_chunk_meta'` is a "subscribable" type but `WebSocketContext` swallows it before dispatch → silent zero-message trap; unused `_exhaustiveCheck` emits TS6133. | Remove from `AnyWebSocketMessage`/`ALL_MESSAGE_TYPES`; document internal consumption. |
| MED-TS-5 (TS-NEW-6) | `CacheManagementPanel/TrackCacheList.tsx:5` vs `standardizedAPIClient.ts:88` | `track_id: string` vs `number` → TS2322; works only via JS coercion. | Make `TrackInfo.track_id: number` (import the shape). |
| MED-TS-6 (TS-NEW-7) | `usePlaybackQueue.ts:104` + 4 queue components | `(Track \| QueueTrack)[]` passed to `track: Track` props → 4 errors; WS-sourced entries have `filepath: undefined`. | Widen the 4 components to `Track \| QueueTrack`; audit `filepath` reads. |

### Design System
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-DS-1 (DS-NEW-1) | `components/navigation/AuroraWaveIcon.tsx:12-34` | App-logo SVG hardcodes 7 colors incl. off-palette Tailwind hues + near-pure-black `#08080a` (violates "no pure black"); glow uses a different cyan than the app accent. | Replace with `tokens.colors.*` + `withOpacity()`. |
| MED-DS-2 (DS-NEW-3) | `index.css:33-35` | `--aurora-gradient/horizontal/vertical` use Tailwind `#06B6D4`/`#F472B6` (in no token); parity test doesn't cover them. | Use spatial-cyan / harmonic-magenta token hexes; add parity assertions. |
| MED-DS-3 (DS-NEW-4) | `index.css:47-55` | `--space-*` scale diverges from `tokens.spacing` at 5/8 steps (DS-1 spacing dimension never reconciled by #3927). | Align values; add `--space-*` parity assertions. |

### API Client
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-AC-1 (AC-NEW-1, +LOW AC-NEW-4) | `hooks/library/useLibraryPagination.ts:146-165` | `loadMore` has `if (response.ok)` with no `else`: non-OK silently dropped (no `error`, no toast, `hasMore` not cleared) → scroll re-fires → retry storm vs a struggling server. `fetchTracks` handles this correctly. | Add `else` setting error + toast; consider `setHasMore(false)`. |
| MED-AC-2 (AC-NEW-2) | `hooks/shared/useStandardizedAPI.ts:314-329` | Partial regression of #3952: initial fetch fixed, but `nextPage`/`prevPage`/`goToPage` call `fetchPage` with no signal and there's no `mountedRef` in `usePaginatedAPI`. | Add `mountedRef` + pass signal in the 3 callbacks. |
| MED-AC-3 (AC-NEW-3) | `components/library/EditMetadataDialog/useMetadataForm.ts:92-145` | `saveMetadata` PUT has no `AbortController` (only the GET was fixed by #3601); `setSuccess`/`setSaving` run after dialog close. | Add `AbortController`/`mountedRef` to the save path. |

### Performance
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-PF-1 (PF-NEW-1) | `hooks/shared/useReduxState.ts:53,112` · `…/artists/useContextMenuActions.ts:27` | `usePlayer()` bundles `currentTime` in its memo → new object every 1 Hz tick; `useContextMenuActions` only needs `play()` yet re-renders `CozyArtistList` at 1 Hz during playback. | Add a state-free `usePlayerActions()` hook for action-only consumers. |
| MED-PF-2 (PF-NEW-3) | `player/QueuePanel/QueuePanel.tsx:228-258` · `QueueTrackItem.tsx:21` | `QueueTrackItem` not `React.memo`'d + 3 inline arrows per item → every hover re-renders all ~15-20 visible items. | `React.memo` + stable per-index handlers. |

### Accessibility (all NEW; missing-label / state / contrast / landmark)
| ID | Location | Issue |
|----|----------|-------|
| MED-A11Y-1 (A11Y-NEW-3) | `components/core/AppTopBarLeftSection.tsx:25` | Mobile hamburger `IconButton` no `aria-label`. |
| MED-A11Y-2 (A11Y-NEW-4) | `components/settings/SettingsDialogHeader.tsx:22` | Settings close `IconButton` no `aria-label`. |
| MED-A11Y-3 (A11Y-NEW-5) | `components/CozyLibraryView/LibrarySearchControls.tsx:66-87` | Scan/Refresh `IconButton`s rely on `Tooltip title` only (no `aria-label`). |
| MED-A11Y-4 (A11Y-NEW-6) | `player/QueueSearchPanel/QueueSearchPanel.tsx:121-162` | 4 duration-filter toggles missing `aria-pressed`. |
| MED-A11Y-5 (A11Y-NEW-8) | `components/shared/MediaCard/MediaCardInfo.tsx:81` | Caption uses `text.disabled` (40% white, ~3.68:1) at 11 px → fails WCAG AA (needs 4.5:1). Use `text.metadata` (60%, ~6.98:1). |
| MED-A11Y-6 (A11Y-NEW-9) | `ComfortableApp.tsx:252-318`, `layouts/Sidebar/SidebarContent.tsx:30` | No landmark regions (`nav`/`main`/`banner`) → no landmark navigation for SR users. |

### Test Coverage
| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-TC-1 (TC-NEW-16) | `player/__tests__/PlaybackControls.test.tsx:450-464` | Asserts disabled `opacity: 0.5` but component uses `0.7` → always fails, never detects regressions. | Update expected value to `0.7`. |
| MED-TC-2 (TC-NEW-17) | `hooks/library/useLibraryPagination.ts`, `useLibraryScan.ts`, `useLibraryStats.ts` | The 3 decomposed library hooks have zero tests (abort-on-supersede, `mountedRef`, `resetPagination` all uncovered). | Add focused tests for pagination reset/append/abort and scan abort/unmount. |

---

## LOW Findings

> Grouped; full snippets in working notes. All NEW unless noted.

**Component Quality** — FE-D1-6 `ConnectionStatusIndicator.tsx` (478 L) and FE-D1-7 `CacheStatsDashboard.tsx` (423 L) exceed 300-line rule; FE-D1-8 inline `<style>` `@keyframes` injection in `ConnectionStatusIndicator`/`BufferingIndicator` (dynamic interpolation re-parses CSSOM per status change); FE-D1-9 `RecentlyTouchedSection` inline `onClick`/`onHoverEnter` defeats `AlbumCard.memo` (sibling of #3929); FE-D1-12 `LoadingSpinner.tsx:38` `Math.random()` gradient id per render leaks `<defs>` nodes → use `useId()`.

**Redux** — RS-NEW-4 `setDuration` doesn't re-clamp `currentTime` on duration shrink (`currentTime > duration` possible; masked by UI clamps); RS-NEW-5 `setIsShuffled`/`setRepeatMode` are the only `queueSlice` reducers not updating `lastUpdated`.

**Hooks** — HC-NEW-1 `useLibraryWithStats` redundant double-abort (sub-hooks already own teardown); HC-NEW-3 `useQueueSearch` module-level `_queueSearchWarned` survives HMR/tests (sibling `useQueueStatistics` already fixed via ref); HC-NEW-5/FE-D3-4 `useLibraryScan.handleScanFolder` lists unstable `useToast` identities in deps (apply `toastRef` pattern from `useLibraryPagination`); HC-NEW-8 `usePlayerControls` inline `onSeek` recreates `seekDebounced`, resetting the debounce timer mid-drag.

**Type Safety** — TS-NEW-8 missing `guards.ts` type guards for `LibraryScanStarted/ScanError/TracksRemoved`; TS-NEW-9 `AlbumArtDisplay sx?: any` should be `SxProps<Theme>` (+ unnecessary `direction as any` in `Stack.tsx`).

**Design System** — DS-NEW-2 shimmer `rgba(255,255,255,0.08)` duplicated across 4 files (token `white.subtle` exists); DS-NEW-5 `EnhancementToggleStyles.ts:71` dynamic white rgba bypasses opacity tokens; DS-NEW-6 `globalStyles.ts:28-31` `--glow-*` raw rgba at opacities inconsistent with `tokens.shadows`; DS-NEW-7 `themeConfig.ts` `cosmicBlue` rebuilt from private constants (token duplicate); DS-NEW-8 `semantics.ts` component tokens hardcode rgba instead of composing `colors.bg.*`; DS-NEW-9 `PresetItem.tsx:47,104` magic font-size numbers; DS-NEW-10 deep relative imports in 3 test files.

**API Client** — AC-NEW-4 UI-state half of MED-AC-1 (`isLoadingMore` clears with no error surfaced); fix together.

**Performance** — PF-NEW-5 `selectFormattedTime`/`selectPlaybackState` take `currentTime` and recompute every second but have **no consumers** — dead weight + a 1 Hz-subscription trap for future importers.

**Accessibility** — A11Y-NEW-11 `ArtistListItem` `aria-label` omits album/track counts; A11Y-NEW-12 `Expanded` (enhancement pane) collapse `IconButton` missing `aria-label`/`aria-expanded`.

**Test Coverage** — TC-NEW-18 `LibraryComponents.test.tsx:113` ambiguous `getByText(/failed/i)` matches two nodes → use `getAllByText`.

---

## Existing / Already-Tracked (confirmed, not re-filed)

- **Open, re-confirmed**: A11Y-1 `MetadataEditorDialog` no dialog role/trap (→ resolved by deleting it, MED-CQ-1); A11Y-6 `ArtistTrackRow` no keyboard activation; A11Y-4 `ThemeToggle` missing `aria-pressed` (label was added); #3929 `CozyAlbumGrid`/`EraSection` inline `onHoverEnter`; #3954 `AlbumCharacterPane` 150 rAF `setIntensity` per stop (partial fix); #3928 `TrackGridView` unvirtualized; FE-NEW-231 `usePlayEnhanced` 20/47 fail (arrow-fn constructor + missing `getMinBufferSamples`/`getFillPercentage` mocks); FE-NEW-232 `usePlayerStateSync` 5/51 fail (`album_art` vs `artwork_url` — possible real protocol bug, see #3505); TC-2/TC-3/TC-7 open.
- **Verified FIXED since 2026-05-29**: CQ-1 (`LibraryViewRouter` hooks #3924), CQ-2/CQ-3 (panel decomposition), RS-1/2/3/4/5, #3582, #3604, #3492, #3501, HC-5 (decomposed correctly), HC-6, HC-10/11, #3575/#3589/#3590, TS-2/4/5/7/8, DS-1(radius/silver/aurora-pink)/DS-2/3/4/5 + #3596-#3640, AC-1/2(initial)/3 + #3601/#3643, #3957/#3606/#3776 (virtualization & 100 ms loop), TC-1/4/5, FE-NEW-230, #3613. The #4079 token split and the #4081 WS-type split are both clean.

---

## Relationships & Shared Root Causes

1. **No CI type gate → 43 errors → 4 real bugs.** CRIT-2 is the umbrella; HIGH-2 (settings-save crash), HIGH-3 (dropped fingerprint statuses), MED-TS-5/6 (queue/cache id mismatches) are the live consequences. Fixing the gate + the 3 root-cause families clears most of them.
2. **Post-unmount setState family.** MED-CQ-5, MED-CQ-6, MED-HC-2, MED-HC-3, MED-AC-2, MED-AC-3 are the same defect (fetch without abort/mount-guard wired to cleanup). One shared `useAbortableFetch`/`mountedRef` utility + a lint rule would prevent recurrence.
3. **`api`-object identity churn from `useRestAPI`.** Root cause of MED-HC-5 (latent refetch loop) and contributes to callback-instability findings. The clean fix — consume the stable `api.get` rather than the wrapper — is reusable across `useLibraryQuery`, `useAlbumsQuery`, `fetchMore`.
4. **WS contract drift.** HIGH-1 (no subscribers), MED-RS-1 (NaN), MED-RS-2 (repeat_mode), MED-TS-3/4 (mastering/chunk-meta types), FE-NEW-232 (`album_art`) all stem from frontend types/handlers lagging the backend WS payloads. A generated contract (or the `sync-contracts` skill) would surface these.
5. **Dead-code + a11y overlap.** MED-CQ-1 (`MetadataEditorDialog`) and existing A11Y-1 are the same file — deletion fixes both. MED-CQ-2 (`AlbumGrid`) deletion also removes the only live consumer of the buggy `useLibraryQuery` path.
6. **`aria-label` on enhancement toggle** ties HIGH-7 (broken integration tests) to the a11y missing-label cluster — one attribute fixes a test suite *and* an accessibility gap.
7. **1 Hz `currentTime` over-subscription.** MED-PF-1 and LOW-PF-NEW-5 both trace to `currentTime` being bundled into broad selectors/hooks; a dedicated actions-only hook + narrowed selectors fix both.

---

## Prioritized Fix Order

1. **CRIT-1** — one-line hook-ordering fix in `RecentlyTouchedSection` (active crash).
2. **CRIT-2 + HIGH-2 + HIGH-3** — add `tsc --noEmit` CI gate and fix the 43 errors (clears 2 runtime bugs and stops future drift). *Single themed PR.*
3. **HIGH-1** — add `usePlayerEventSync` for the 4 unhandled WS events (player-state correctness).
4. **HIGH-5** — focus trap on `QueueSearchPanel` (keyboard usability).
5. **HIGH-4** — `dispose()` the PCM buffer on track switch (memory/audio stability).
6. **HIGH-6 / HIGH-7 / HIGH-8** — repair the 3 broken/missing critical-path test suites (restores regression safety on enhancement + play paths). *HIGH-7 fix doubles as an a11y fix.*
7. **MEDIUM post-unmount cluster** (CQ-5/6, HC-2/3, AC-2/3) via a shared abort/mount utility.
8. **MEDIUM Redux/WS validation** (RS-1 NaN, RS-2 repeat_mode) + **MED-HC-5** (delete or fix the latent `useLibraryQuery` loop) + dead-code deletions (CQ-1/CQ-2).
9. **MEDIUM a11y labels/landmarks/contrast** (A11Y-1..6) — mostly single-attribute changes.
10. **LOW** — token-bypass rgba sweep, size-rule refactors, `useId()` in `LoadingSpinner`, dead-selector cleanup.

---

*Generated by `/audit-frontend` (9 dimensions, deep). GitHub was offline; dedup used local audit reports + `.claude/issues/` snapshots. Verify `#NNNN` issue states before publishing.*
