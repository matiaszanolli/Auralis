# Incremental Audit — 2026-03-02

**Commit Range**: `HEAD~10..HEAD` (ebb3e513..1e60b499)
**Auditor**: Claude Opus 4.6
**Methodology**: Delta audit per `.claude/commands/audit-incremental.md` and `_audit-common.md`

---

## 1. Change Summary

| Commits | Theme |
|---------|-------|
| `8225beed` | **refactor: consolidate Track type hierarchy** — Major refactor replacing ~15 local Track interfaces with centralized domain types (`PlayerTrack`, `QueueTrack`, `LibraryTrack`, `DetailTrack`, `TrackRef`) in `types/domain.ts` |
| `215e8ea4` | **fix: replace as-any casts in usePlaybackState** — Typed `RawPlayerStateData` interface and `transformPlayerState()` function eliminate `as any` casts |
| `f6bc9ad3` | **fix: add dialog accessibility** — New `useDialogAccessibility` hook with focus trapping and Escape key for custom modals |
| `bef066b1` | **fix: replace raw fetch with apiRequest** — EnhancementContext and settingsService migrated to centralized `post()` utility |
| `6e332b81` | **fix: tsc type-checking and restrict API retries** — Added `type-check` script, non-idempotent methods no longer retry by default |
| `578cd901`, `ebb3e513` | **fix: rollup CVE override** — pnpm/npm overrides for rollup >=4.59.0 |
| `6c5f6e95` | **chore: bump Electron 27→35** — Major version jump in desktop wrapper |
| `60ffac95`, `3ea749dc` | **chore: dep bumps** — aiohttp 3.13.2→3.13.3, python-multipart 0.0.20→0.0.22 |

**45 files changed** across frontend types, components, hooks, services, store, config, and desktop.

**Key Themes**: Type safety hardening, accessibility improvements, API centralization, dependency maintenance.

---

## 2. High-Risk Changes

### Domain: Frontend Store (MEDIUM risk)

- `playerSlice.ts`: Local `Track` interface replaced with `PlayerTrack` from domain. Backward-compat `export type Track = PlayerTrack` added.
- `queueSlice.ts`: Import changed from `playerSlice.Track` to `QueueTrack` from domain.
- **Assessment**: Structurally safe. `PlayerTrack` and `QueueTrack` are identical `Pick<>` subsets matching the old interfaces. No runtime behavior change.

### Domain: Frontend Hooks (MEDIUM risk)

- `usePlaybackState.ts`: `as any` casts replaced with typed `RawPlayerStateData` and `transformPlayerState()`. Backend snake_case → frontend camelCase mapping centralized.
- `useReduxState.ts`: `any` parameter types replaced with `PlayerTrack` and `QueueTrack`.
- `useDialogAccessibility.ts`: **New hook** — focus trapping, Escape key, focus restoration for custom modal dialogs.
- **Assessment**: Type changes are sound. The `transformPlayerState()` function correctly maps all fields with sensible defaults. Dialog hook delegates to existing `focusManager.createFocusTrap()`.

### Domain: Desktop (HIGH risk)

- `desktop/package.json`: Electron bumped from `^27.3.11` to `^35.7.5` (8 major versions).
- **Assessment**: `electron-builder` remains at `^24.13.3` and may not support Electron 35. Desktop app code (`main.js`) was NOT updated and uses deprecated Electron API (`new-window` event).

---

## 3. Findings

### INC-01: Electron 27→35 bump without electron-builder or main process update
- **Severity**: MEDIUM
- **Changed File**: `desktop/package.json` (commit: `6c5f6e95`)
- **Status**: NEW
- **Description**: Electron was bumped 8 major versions (27→35), but `electron-builder` remains at `^24.13.3` (released for Electron ~25–26 era). Additionally, `desktop/main.js:641` uses `contents.on('new-window')`, an event deprecated since Electron 12 and likely removed by Electron 35. The main window already has the modern `setWindowOpenHandler()` (line 332), but the global security catch-all for child webContents is now dead code.
- **Evidence**:
  ```json
  // desktop/package.json
  "electron": "^35.7.5",        // bumped from ^27.3.11
  "electron-builder": "^24.13.3" // NOT updated
  ```
  ```javascript
  // desktop/main.js:640-644 — deprecated API
  app.on('web-contents-created', (event, contents) => {
    contents.on('new-window', (event, navigationUrl) => {
      event.preventDefault();
      require('electron').shell.openExternal(navigationUrl);
    });
  });
  ```
- **Impact**: Desktop builds may fail or produce broken packages. Global `new-window` security handler is non-functional, allowing child webContents to open new windows without restriction.
- **Suggested Fix**: (1) Bump `electron-builder` to a version supporting Electron 35. (2) Replace `new-window` with `setWindowOpenHandler()` in the `web-contents-created` handler. (3) Verify the desktop build succeeds with the new versions.

---

### INC-02: useDialogAccessibility Escape key fails when dialog has no focusable elements
- **Severity**: MEDIUM
- **Changed File**: `auralis-web/frontend/src/hooks/shared/useDialogAccessibility.ts` (commit: `f6bc9ad3`)
- **Status**: NEW
- **Description**: The new `useDialogAccessibility` hook delegates entirely to `focusManager.createFocusTrap()` for Escape key handling. However, `createFocusTrap()` in `a11y/focusManagement.ts:114-115` returns a no-op when the container has no focusable elements — meaning the Escape keydown listener is never attached. Dialogs that render with a loading state (no buttons initially) will not respond to Escape.
- **Evidence**:
  ```typescript
  // a11y/focusManagement.ts:114-115
  const focusableElements = this.getFocusableElements(container);
  if (focusableElements.length === 0) {
    return () => {};  // ← Escape handler never attached
  }
  ```
- **Impact**: Any dialog using `useDialogAccessibility` that has no focusable elements at mount time will ignore Escape key presses. Current usages (CacheHealthWidget, CacheManagementPanel, QueueManager) all render buttons immediately, so this doesn't manifest yet — but the hook is exported as a shared utility and the behavior is undocumented.
- **Suggested Fix**: Attach the Escape key listener unconditionally, even when there are no focusable elements. Move the Escape handler out of the focus trap logic:
  ```typescript
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && onEscape) {
      event.preventDefault();
      onEscape();
    }
  };
  container.addEventListener('keydown', handleKeyDown);
  // Then separately set up focus trap if focusable elements exist
  ```

---

### INC-03: Nine orphaned backward-compat Track re-exports
- **Severity**: LOW
- **Changed File**: Multiple (commit: `8225beed`)
- **Status**: NEW
- **Description**: The Track type consolidation added `export type Track = <DomainType>` re-exports in 9 files for backward compatibility. However, all consumers were updated in the same commit to import directly from `@/types/domain`, leaving every re-export orphaned. These violate the project's "avoid backward-compat hacks" principle (CLAUDE.md).
- **Evidence**: `grep` for imports of `Track` from any of these modules returns zero results:
  - `playerSlice.ts` → `export type Track = PlayerTrack` (0 consumers)
  - `useLibraryData.ts` → `export type Track = LibraryTrack` (0 consumers)
  - `useLibraryWithStats.ts` → `export type Track = LibraryTrack` (0 consumers)
  - `TrackListView.tsx` → `export type Track = LibraryTrack` (0 consumers)
  - `TrackRow.tsx` → `export type Track = LibraryTrack` (0 consumers)
  - `useAlbumDetails.ts` → `export type Track = DetailTrack` (0 consumers)
  - `useArtistDetailsData.ts` → `export type Track = DetailTrack` (0 consumers)
  - `playlistService.ts` → `export type { Track }` (0 consumers)
  - `useLibraryData.ts` duplicate export (0 consumers)
- **Impact**: Dead code that adds confusion. Future developers may import from these re-exports instead of the canonical `@/types/domain`.
- **Suggested Fix**: Remove all orphaned `export type Track = ...` re-exports.

---

### INC-04: Track transformation logic duplicated 4 times across library hooks
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/library/useLibraryData.ts`, `useLibraryWithStats.ts` (commit: `8225beed`)
- **Status**: NEW
- **Description**: The backend→frontend track mapping (snake_case fields → camelCase `LibraryTrack`) is duplicated identically 4 times: twice in `useLibraryData.ts` (initial load + pagination) and twice in `useLibraryWithStats.ts` (initial load + pagination). Per the DRY principle, this should be a shared function.
- **Evidence**:
  ```typescript
  // Identical block appears 4 times:
  const transformedTracks: Track[] = (data.tracks || []).map((track: any) => ({
    id: track.id,
    title: track.title ?? '',
    artist: Array.isArray(track.artists) && track.artists.length > 0
      ? track.artists[0] : track.artist || 'Unknown Artist',
    album: track.album ?? '',
    albumId: track.album_id ?? undefined,
    duration: track.duration ?? 0,
    filepath: track.filepath ?? track.file_path ?? '',
    artworkUrl: track.artwork_url ?? track.album_art ?? null,
    genre: track.genre ?? null,
    year: track.year ?? null,
    favorite: track.favorite ?? undefined,
  }));
  ```
- **Impact**: Maintenance burden — any backend field rename must be updated in 4 places. Risk of drift if one instance is updated but others are missed.
- **Suggested Fix**: Extract a shared `transformBackendTrack(raw: any): LibraryTrack` function in `@/types/domain.ts` or a utility module, similar to the existing `transformPlayerState()`.

---

### INC-05: No tests for useDialogAccessibility hook
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/shared/useDialogAccessibility.ts` (commit: `f6bc9ad3`)
- **Status**: NEW
- **Description**: The new `useDialogAccessibility` hook provides focus trapping, Escape key dismissal, and focus restoration — all behavior that warrants unit testing. No tests were added for the hook itself, and the three consuming components (CacheHealthWidget, CacheManagementPanel, QueueManager) also lack tests for the new accessibility behavior.
- **Evidence**: No test files found matching `useDialogAccessibility`:
  ```
  $ find auralis-web/frontend/src -name "*DialogAccessibility*" -o -name "*dialogAccessibility*"
  # Only the source file — no test file
  ```
- **Impact**: Regressions in focus trapping or Escape key behavior would go undetected.
- **Suggested Fix**: Add tests covering: (1) Focus moves into dialog on mount, (2) Tab wraps within dialog, (3) Escape calls onClose, (4) Focus restores on unmount.

---

### INC-06: usePlayerAPI uses full Track type for WebSocket state with limited fields
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/player/usePlayerAPI.ts` (commit: `8225beed`)
- **Status**: NEW
- **Description**: `usePlayerAPI` was updated to import `Track` from `@/types/domain` (the full 20+ field interface). But the WebSocket `player_state` messages only populate `TrackInfo` fields (id, title, artist, duration, album, artworkUrl). The hook's `PlayerState.currentTrack` and `PlayerState.queue` claim to be `Track[]` but only contain a subset of fields at runtime.
- **Evidence**:
  ```typescript
  // hooks/player/usePlayerAPI.ts:29
  import type { Track } from '@/types/domain';

  interface PlayerState {
    currentTrack: Track | null;  // Claims full Track
    queue: Track[];              // Claims full Track[]
  }

  // But WebSocket handler (line 269-277) sets state from raw backend data:
  currentTrack: state.current_track || null,  // Only has TrackInfo fields
  queue: state.queue || [],                   // Only has TrackInfo fields
  ```
- **Impact**: Consumers accessing `currentTrack.genre`, `currentTrack.filepath`, etc. from `usePlayerAPI` will get `undefined` despite the type suggesting these fields exist. All extra fields are optional so TypeScript won't flag this.
- **Suggested Fix**: Use `PlayerTrack` or `TrackInfo` instead of the full `Track` type in `usePlayerAPI`'s `PlayerState` interface.

---

## 4. Cross-Layer Impact

| Changed Layer | Impact Check | Status |
|--------------|-------------|--------|
| Domain types (`types/domain.ts`) | All component imports updated? | **OK** — all 30+ consumers migrated |
| Redux store (playerSlice, queueSlice) | Reducers compatible with new types? | **OK** — `PlayerTrack`/`QueueTrack` are structural matches |
| WebSocket types (`types/websocket.ts`) | `PlayerStateMessage.data` typed correctly? | **OK** — now `RawPlayerStateData`, transformer maps correctly |
| API endpoints (`config/api.ts`) | Backend routes match new ENDPOINTS? | **OK** — URLs unchanged, only location moved to constants |
| EnhancementContext → apiRequest | Error handling equivalent? | **OK** — `post()` throws `APIRequestError` on failure; callers catch and set error state |
| settingsService.triggerLibraryScan | Behavior change? | **MINOR** — old code silently ignored errors; new `post()` throws on failure. If caller doesn't catch, results in unhandled promise rejection |
| Desktop (Electron 35) → electron-builder | Build compatibility? | **RISK** — see INC-01 |

---

## 5. Missing Tests

| Changed Code | Test Coverage |
|-------------|--------------|
| `useDialogAccessibility` (new hook) | **No tests** — see INC-05 |
| `transformPlayerState()` (new function) | **No tests** — pure function ideal for unit testing |
| Track type re-exports (9 files) | N/A — type-only changes |
| API client retry restriction | **Tests added** — 5 new test cases in `standardizedAPIClient.test.ts` |
| EnhancementContext → `post()` migration | **No new tests** — relies on existing apiRequest tests |
| `useLibraryData` / `useLibraryWithStats` transforms | **No new tests** — transformation logic untested |
