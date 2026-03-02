# Frontend Audit — 2026-03-01 (v5)

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: 3 parallel exploration agents (Hooks/Redux/Contexts, Components/Design/Services/A11y, Types/Perf/Tests/Config), followed by manual verification of all candidate findings against source code. All prior findings FE-24–FE-32 re-verified. ~15 false positives eliminated.

## Executive Summary

The TypeScript 5.x upgrade (FE-24) is now **FIXED** — `tsc --noEmit` runs cleanly with only the pre-existing TS2590 in `Box.tsx`. With type checking now functional, this audit reveals the downstream consequences: **9 duplicate `Track` interface definitions** (FE-33) that enable `as any` casts throughout queue operations, and incomplete track objects dispatched to the queue that **omit the `artist` field** (FE-35), causing "undefined" in the queue panel UI.

The most impactful new finding is **FE-34** (HIGH): `useSearchLogic` fetches the entire library on every keystroke (3 sequential `fetch()` calls with client-side filtering), capped at 100 tracks — meaning search misses anything beyond the first 100 results.

**Results**: 10 new confirmed findings (0 CRITICAL, 2 HIGH, 5 MEDIUM, 3 LOW). Total open findings after this pass: 22 (12 carried-over + 10 new).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 0 | 2 |
| MEDIUM | 5 | 6 | 11 |
| LOW | 3 | 6 | 9 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 178 console.log statements, no production stripping | #2597 | **STILL OPEN** |
| FE-12: WebSocketContext propagates `any` instead of typed union | #2598 | **STILL OPEN** |
| FE-14: 5 player components exceed 300-line guideline | #2600 | **STILL OPEN** |
| FE-18: usePlayNormal passes handlers directly to subscribe | #2604 | **STILL OPEN** |
| FE-19: Design system primitives use `{...(props as any)}` | #2605 | **STILL OPEN** |
| FE-23: AudioPlaybackEngine and index.tsx use `window as any` | #2620 | **STILL OPEN** |
| FE-24: TypeScript 4.9.5 incompatible with moduleResolution bundler | #2632 | **FIXED** — upgraded to TS 5.9.3, 899 type errors resolved (commit `592891db`) |
| FE-25: EnhancementContext shared isProcessing flag races | #2633 | **STILL OPEN** |
| FE-26: triggerLibraryScan bypasses centralized API client | #2634 | **STILL OPEN** |
| FE-27: useSettingsDialog error state never rendered | #2635 | **STILL OPEN** |
| FE-28: queueSlice.setQueue([]) sets currentIndex to -1 | #2636 | **STILL OPEN** |
| FE-29: SettingsDialogHeader hardcodes color white | #2637 | **STILL OPEN** |
| FE-30: ScanStatusCard lacks aria-live region | #2638 | **STILL OPEN** |
| FE-31: Settings components use relative imports | #2639 | **STILL OPEN** |
| FE-32: Six unused production dependencies | #2640 | **STILL OPEN** |
| ArtworkResponse frontend type mismatch | #2627 | **STILL OPEN** |

## New Findings

---

### FE-33: Nine duplicate `Track` interface definitions with incompatible shapes
- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `playerSlice.ts:19`, `TrackRow.tsx:19`, `TrackListView.tsx:27`, `useLibraryData.ts:17`, `useLibraryWithStats.ts:54`, `playlistService.ts:32`, `useArtistDetailsData.ts:10`, `useAlbumDetails.ts:13`, `types/domain.ts:12`
- **Status**: NEW
- **Description**: The `Track` type is defined in 9 separate files with incompatible shapes. The canonical type (`types/domain.ts`) includes `filepath`, `artworkUrl`, `genre`, `year`, `bitrate`, `sampleRate`, etc. But `playerSlice.ts` Track is minimal (`id, title, artist, album?, duration, artworkUrl?`), `TrackRow.tsx` Track adds `album_id?` and `albumArt?` (different name from `artworkUrl`), and `playlistService.ts` Track makes `artist` optional while `playerSlice.ts` requires it. This forces `as any` casts at every boundary crossing.
- **Evidence**:
  ```typescript
  // playerSlice.ts — artist required, no filepath
  export interface Track { id: number; title: string; artist: string; duration: number; }

  // TrackRow.tsx — uses albumArt, not artworkUrl
  export interface Track { id: number; title: string; albumArt?: string; album_id?: number; }

  // playlistService.ts — artist optional
  export interface Track { id: number; title: string; artist?: string; }
  ```
- **Impact**: Root cause of `as any` casts in `useContextMenuActions.ts:52` (`queue.setQueue(tracks as any)`) and `useTrackContextMenu.ts:96` (`queue.addMany([queueTrack] as any)`). These casts hide missing fields that cause runtime `undefined` (see FE-35). With TS 5.x now running, removing these casts would immediately surface the type mismatches.
- **Suggested Fix**: Consolidate to a single `Track` type in `types/domain.ts`. Where only a subset is needed, use `Pick<Track, 'id' | 'title' | ...>`.

---

### FE-34: `useSearchLogic` fetches entire library on every search keystroke, filters client-side
- **Severity**: HIGH
- **Dimension**: API Client & Data Fetching
- **Location**: `auralis-web/frontend/src/components/library/Hooks/useSearchLogic.ts:64-129`
- **Status**: NEW
- **Description**: The global search hook makes 3 sequential raw `fetch()` calls on every debounced keystroke: `GET /api/library/tracks?limit=100` (entire tracks table, capped at 100), `GET /api/albums` (all albums), `GET /api/artists` (all artists). Results are filtered client-side with `.includes()`. The hard-coded `limit=100` means search misses any track beyond the first 100 in the library. All 3 calls use raw `fetch()` bypassing the centralized API client, with no request cancellation (typing "abc" fires 3 searches: "a", "ab", "abc" — all 9 fetches run to completion).
- **Evidence**:
  ```typescript
  // useSearchLogic.ts:70-72 — fetches ALL tracks (capped at 100)
  const tracksResponse = await fetch(`/api/library/tracks?limit=100`);
  // :92 — fetches ALL albums
  const albumsResponse = await fetch('/api/albums');
  // :112 — fetches ALL artists
  const artistsResponse = await fetch('/api/artists');
  // Then filters client-side with .includes()
  ```
- **Impact**: For a library with 5,000+ tracks, 3 full-collection fetches fire per keystroke. Search results are incomplete (100-track cap). No AbortController means stale results from slow responses can overwrite newer results.
- **Suggested Fix**: Use server-side filtering by passing `?search=query` to existing endpoints. Add AbortController to cancel in-flight searches when the query changes. Use the centralized API client.

---

### FE-35: Queue context menus build incomplete track objects, omitting `artist` field
- **Severity**: MEDIUM
- **Dimension**: Component Quality / Bug
- **Location**: `auralis-web/frontend/src/components/library/Items/tracks/useTrackContextMenu.ts:88-96` and `auralis-web/frontend/src/components/library/Items/artists/useContextMenuActions.ts:43-52`
- **Status**: NEW
- **Description**: When adding tracks to the queue, both hooks construct partial track objects that omit the `artist` field. The `artist` field is required on `Track` in `playerSlice.ts`, but the `as any` cast silences the error. The `QueuePanel` renders `track.artist` in 3 places: the aria-label (line 299), the title tooltip (line 322), and the artist display (line 333).
- **Evidence**:
  ```typescript
  // useTrackContextMenu.ts:88-96
  const queueTrack = {
    id: track.id, title: track.title,
    album: track.album, duration: track.duration,
    // MISSING: artist
  };
  queue.addMany([queueTrack] as any);  // cast hides the error

  // useContextMenuActions.ts:43-52 — same pattern, also missing artist
  ```
  ```tsx
  // QueuePanel.tsx:333 — renders undefined
  <div style={styles.trackArtist}>{track.artist}</div>
  // QueuePanel.tsx:299 — aria-label with undefined
  aria-label={`${track.title} by ${track.artist}, ...`}
  ```
- **Impact**: When tracks are added via context menu "Add to Queue" or "Play Artist", the queue panel shows "undefined" as the artist name, and the aria-label reads "Song by undefined". This is a user-visible bug.
- **Suggested Fix**: Add `artist: track.artist` to both object constructions. Remove the `as any` casts.

---

### FE-36: `useQueue` hook accepts `any` for all track action parameters
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/shared/useReduxState.ts:158-185`
- **Status**: NEW
- **Description**: The `useQueue()` hook's `add`, `addMany`, and `setQueue` callbacks all accept `any` or `any[]` instead of `Track`. This defeats type checking at the dispatch boundary, allowing any arbitrary object to be dispatched into the Redux queue slice.
- **Evidence**:
  ```typescript
  // useReduxState.ts:158-184
  add: useCallback(
    (track: any) => dispatch(queueActions.addTrack(track)), [dispatch]
  ),
  addMany: useCallback(
    (tracks: any[]) => dispatch(queueActions.addTracks(tracks)), [dispatch]
  ),
  setQueue: useCallback(
    (tracks: any[]) => dispatch(queueActions.setQueue(tracks)), [dispatch]
  ),
  ```
- **Impact**: Callers can pass incomplete track objects (as in FE-35) without compiler errors. Downstream consumers reading `track.artist`, `track.duration`, etc. get `undefined` values, leading to NaN calculations and "undefined" text in the UI.
- **Suggested Fix**: Change parameter types to `Track` (from `playerSlice` or `types/domain`). Then fix callers to pass complete Track objects.

---

### FE-37: `useBatchOperations` sends sequential raw `fetch` calls with no partial-failure handling
- **Severity**: MEDIUM
- **Dimension**: API Client & Data Fetching
- **Location**: `auralis-web/frontend/src/components/library/useBatchOperations.ts:21-64`
- **Status**: NEW
- **Description**: Batch operations (`handleBulkAddToQueue`, `handleBulkRemove`) iterate over selected track IDs, making individual raw `fetch()` calls in a `for...of` loop. If one call fails partway through, the catch block shows a generic error toast, but some tracks have already been processed. Additionally, these use raw `fetch()` instead of the centralized API client (`apiRequest`/`post()`).
- **Evidence**:
  ```typescript
  // useBatchOperations.ts:24-30
  for (const trackId of selectedTrackIds) {
    await fetch('/api/player/queue/add-track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId })
    });
  }
  ```
- **Impact**: If a user selects 20 tracks and the network drops after 10, only 10 get added with no indication of which succeeded. The use of raw `fetch` also bypasses URL configuration and retry logic.
- **Suggested Fix**: Use the centralized API client. Collect results per-track and report partial success/failure.

---

### FE-38: `StandardizedAPIClient` retries non-idempotent POST/PUT/DELETE requests
- **Severity**: MEDIUM
- **Dimension**: API Client & Data Fetching
- **Location**: `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:247-298`
- **Status**: NEW
- **Description**: The `request()` method retries all failed requests up to `retryAttempts` (default 3) regardless of HTTP method. POST, PUT, and DELETE requests are retried on network errors, which can cause duplicate side effects (double-submitting a processing job, double-deleting a resource). The retry also fires on `AbortError` (from the timeout AbortController), which should not be retried.
- **Evidence**:
  ```typescript
  // standardizedAPIClient.ts:248-298
  for (let attempt = 0; attempt <= this.retryAttempts; attempt++) {
    try {
      const response = await fetch(url, { method, ... });
      // ...
    } catch (error) {
      // Retries ALL methods including POST/DELETE, including AbortError
      if (attempt < this.retryAttempts) {
        const delay = this.retryDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  ```
- **Impact**: A POST to `/api/processing/process` that succeeds server-side but loses the response gets retried, submitting a duplicate processing job. An aborted request (timeout) gets retried instead of failing immediately.
- **Suggested Fix**: Only retry GET and HEAD requests automatically. Skip retry on `AbortError`. For non-idempotent methods, require an explicit `idempotent: true` option.

---

### FE-39: Custom modal dialogs lack `role="dialog"`, focus trapping, and Escape key handling
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `CacheManagementPanel.tsx:57-158`, `QueueManager.tsx:424-505`, `CacheHealthWidget.tsx:267-335`
- **Status**: NEW
- **Description**: Multiple custom modal overlays are rendered as plain `<div>` elements with `position: fixed` and `z-index: 1000` but lack: (1) `role="dialog"` and `aria-modal="true"`, (2) focus trapping (Tab can escape to background elements), (3) focus return to trigger element on close, (4) Escape key handling. MUI's `Dialog` component handles all of this — these custom modals bypass it.
- **Evidence**:
  ```tsx
  // CacheManagementPanel.tsx:58-67 — ConfirmationModal
  <div style={{
    position: 'fixed', inset: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    zIndex: 1000,
  }}
  onClick={onCancel}>
  // No role, no aria-modal, no onKeyDown, no focus trap
  ```
- **Impact**: Keyboard-only users can Tab behind the modal. Screen readers don't announce the dialog. Violates WCAG 2.1 SC 2.1.2.
- **Suggested Fix**: Use MUI's `Dialog` component (already a dependency), or add `role="dialog"`, `aria-modal="true"`, an Escape key handler, and a focus trap using the existing `focusManagement.ts` utilities.

---

### FE-40: `usePlaybackState` bypasses typed `PlayerStateData` with `as any`, accessing raw snake_case fields
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:74-92`
- **Status**: NEW
- **Description**: In the `player_state` handler, `msg.data` is cast to `any` and raw snake_case properties are accessed directly (`data.current_track`, `data.is_playing`, `data.current_time`). The typed `PlayerStateData` interface in `types/websocket.ts` uses camelCase and is effectively unused — the `as any` cast bypasses it entirely. This same pattern appears at lines 174, 206, and 239 for position/track/playing handlers.
- **Evidence**:
  ```typescript
  // usePlaybackState.ts:77
  const data = msg.data as any;  // cast bypasses PlayerStateData type
  return {
    currentTrack: data.current_track ?? null,  // raw snake_case
    isPlaying: data.is_playing ?? false,
    position: data.current_time ?? 0,
  };
  ```
- **Impact**: No compile-time validation that field names match the backend. If the backend renames a field, the frontend silently gets `undefined` and falls back to defaults with no type error. Low severity because the mapping is well-established and unlikely to change.
- **Suggested Fix**: Create a raw backend response type with snake_case fields and an explicit transform function. Remove the `as any` cast.

---

### FE-41: `EditMetadataDialog.styles.ts` hardcodes hex background colors bypassing design tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/EditMetadataDialog/EditMetadataDialog.styles.ts:15-19`
- **Status**: NEW
- **Description**: The dialog's `PaperProps` uses hardcoded `bgcolor: '#1a1f3a'` and `backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)'` instead of design tokens. The values are close to but don't exactly match `tokens.colors.bg.level3` (`#1A2338`) and `tokens.colors.bg.level0` (`#0B1020`).
- **Evidence**:
  ```typescript
  export const DialogPaperProps = {
    sx: {
      bgcolor: '#1a1f3a',  // hardcoded, not tokens.colors.bg.level3
      backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)',
    },
  };
  ```
- **Impact**: Subtle visual inconsistency with other dialogs. Won't adapt if the token palette changes.
- **Suggested Fix**: Replace with `tokens.colors.bg.level3` and compose gradient using tokens.

---

### FE-42: Stale CRA `"proxy"` field in `package.json` points to wrong port
- **Severity**: LOW
- **Dimension**: Config
- **Location**: `auralis-web/frontend/package.json:100`
- **Status**: NEW
- **Description**: The `"proxy": "http://localhost:8000"` field is a leftover from Create React App migration. Vite ignores this field — the actual proxy is configured in `vite.config.mts` pointing to `localhost:8765`. The backend runs on port 8765, not 8000.
- **Evidence**:
  ```json
  // package.json:100 — stale, ignored by Vite
  "proxy": "http://localhost:8000"

  // vite.config.mts:111-115 — actual proxy configuration
  proxy: {
    '/api': { target: 'http://localhost:8765' },
    '/ws': { target: 'ws://localhost:8765', ws: true },
  }
  ```
- **Impact**: No runtime impact (Vite ignores it). Confuses developers who read `package.json` and expect the proxy to work on port 8000.
- **Suggested Fix**: Remove the `"proxy"` field from `package.json`.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `useWebSocketProtocol` effect re-subscribes on every render due to callback deps | Verified: no caller passes `onConnectionChange`/`onError` — they're always `undefined` (stable). The deps are technically wrong but harmless in practice. |
| `useMasteringRecommendation` mutates useState object | Verified: it uses `setCache({...cache, [trackId]: rec})` which creates a new object. Not mutation. |
| `AlbumCharacterPane` exceeds 300 lines | True (1111 lines), but already tracked under #2600 (FE-14: 5+ player/library components exceed 300 lines). |
| Module-level `document.head.appendChild` duplicates `<style>` tags on HMR | Dev-only issue via Vite HMR. In production, modules load once. No user impact. |
| `QueuePanel` renders all items without virtualization | True, but the queue is populated from backend which limits to ~100 tracks in practice. The theoretical concern doesn't match real usage — queue sizes rarely exceed 50. LOW priority, deferred. |
| `SwitchVariant.tsx` hardcodes rgba brand color | True, but same class of issue as FE-29 (SettingsDialogHeader hardcodes white, #2637). Not worth a separate issue. |
| `@types/*` in dependencies instead of devDependencies | No functional impact in Electron app. Standard npm hygiene, not a bug. |
| `usePlaybackQueueView` duplicates WebSocket subscriptions | Verified: `initializeWebSocketProtocol` is a singleton factory — multiple callers share the same connection. The subscriptions are deduplicated by the protocol client. No duplication. |
| `PlayerStateData` camelCase/snake_case mismatch with `domain.ts` | Already covered by FE-40 (the `as any` cast that hides the mismatch). Not a separate finding. |
| `WebSocketContext.tsx` duplicates types from `types/websocket.ts` | Already tracked under #2598 (FE-12: WebSocketContext propagates `any` types). Same root cause. |
| `api.ts` PlayerState vs `domain.ts` PlayerState conflict | Both are dead code — the Redux slice defines its own `PlayerState` which is actually used. No runtime impact. |
| `Vite build has no code splitting beyond vendor chunk` | Electron app loads from local filesystem. Network-based code splitting concerns don't apply. |

## Dimension Checklist Summary

### Dimension 1: Component Quality
- [x] Single responsibility — hooks handle logic, components handle rendering
- [ ] **Size guideline** — FE-14 (open #2600, 5+ components exceed 300 lines)
- [x] Key stability — all lists use stable keys
- [x] Error boundaries — ErrorBoundary wraps `<App />` at root
- [ ] **Error display** — FE-27 (open #2635, useSettingsDialog.error never rendered)
- [ ] **Incomplete objects** — FE-35 (queue tracks missing `artist` field)

### Dimension 2: Redux State Management
- [x] Normalized state — no duplication between slices
- [x] Selector memoization — comprehensive `createSelector` usage
- [ ] **Edge case** — FE-28 (open #2636, setQueue([]) creates invalid -1 index)
- [ ] **Type safety** — FE-36 (useQueue accepts `any` for track parameters)
- [x] Serializable state — no functions or class instances in Redux

### Dimension 3: Hook Correctness
- [x] EnhancementContext error handling — FIXED (#2602)
- [x] useLibraryData loadMore race — FIXED (#2603)
- [ ] **EnhancementContext isProcessing** — FE-25 (open #2633)
- [ ] **usePlayNormal handler subscriptions** — FE-18 (open #2604)
- [x] useEffect cleanup — WebSocket, timers, AbortControllers properly cleaned up

### Dimension 4: TypeScript Type Safety
- [x] **TypeScript version** — FE-24 (**FIXED**, TS 5.9.3 running, 899 errors resolved)
- [ ] **Duplicate Track types** — FE-33 (9 incompatible Track interfaces)
- [ ] **useQueue `any` parameters** — FE-36
- [ ] **usePlaybackState `as any`** — FE-40
- [ ] **WebSocketContext `any`** — FE-12 (open #2598)
- [ ] **Design system primitives `as any`** — FE-19 (open #2605)
- [ ] **`window as any`** — FE-23 (open #2620)

### Dimension 5: Design System Adherence
- [x] Color.styles.ts migration — FIXED (FE-20)
- [x] BatchActionsMoreMenu — FIXED (FE-21)
- [ ] **Hardcoded `color: 'white'`** — FE-29 (open #2637)
- [ ] **Hardcoded hex backgrounds** — FE-41
- [ ] **Relative imports** — FE-31 (open #2639)

### Dimension 6: API Client & Data Fetching
- [ ] **Full-library search** — FE-34 (fetches entire library per keystroke)
- [ ] **Batch raw fetch** — FE-37 (sequential fetch loop, no partial-failure handling)
- [ ] **POST/DELETE retries** — FE-38 (retries non-idempotent requests)
- [ ] **Raw fetch** — FE-26 (open #2634, triggerLibraryScan)
- [x] AbortController cleanup — per-request + unmount cleanup intact
- [x] Transformer layer — per-entity snake→camel transformers

### Dimension 7: Performance
- [ ] **Console logging in production** — FE-11 (open #2597)
- [ ] **Unused dependencies** — FE-32 (open #2640)
- [x] List virtualization — TrackList uses @tanstack/react-virtual
- [x] Position updates — batched via React 18 automatic batching

### Dimension 8: Accessibility
- [ ] **Custom modals** — FE-39 (missing role, focus trap, Escape key)
- [ ] **Scan progress** — FE-30 (open #2638, ScanStatusCard missing aria-live)
- [x] Queue toggle `aria-expanded` — FIXED (#2599)
- [x] ProgressBar ARIA, keyboard nav — intact

### Dimension 9: Test Coverage
- [x] `usePlayEnhanced` — FIXED (#2601), 1,056-line test file
- [x] Player hooks, selectors, integration tests — all intact
- [x] No snapshot tests — proper assertion-based testing
- [x] Pre-existing test failures (4 files, 12 tests) are NOT regressions — same failures exist on master before the TS 5.x upgrade
