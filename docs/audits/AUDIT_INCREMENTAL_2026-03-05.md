# Incremental Audit: 2026-03-05

**Commit Range**: `HEAD~10..HEAD` (258fa3c3..3e9c7a49)
**Auditor**: Claude Opus 4.6
**Date**: 2026-03-05

## 1. Change Summary

| Commit | Description |
|--------|-------------|
| 3e9c7a49 | fix: use granular selectors in usePlaybackProgress to avoid excess re-renders (#2699) |
| 86caa13e | fix: collapse PathValidationError into generic 400 to prevent filesystem enumeration (#2629) |
| f2992f94 | fix: stop leaking raw exception messages in enhancement router responses (#2666) |
| 3e5b5450 | fix: render error state from useSettingsDialog in SettingsDialog UI (#2635) |
| c2cc9c0e | fix: return copy instead of alias for silent audio in normalize() (#2683) |
| 82c3eaaf | fix: memoize shortcutsToRegister to prevent effect churn on every render (#2696) |
| a5adfb72 | fix: virtualize QueuePanel list with @tanstack/react-virtual (#2698) |
| f0f64473 | docs: add 2026-03-04 frontend audit report (FE-43 through FE-51) |
| 3d0bbda8 | refactor: remove 9 orphaned backward-compat Track re-exports (#2662) |
| 258fa3c3 | fix: replace relative imports with @/ absolute paths in settings components (#2639) |

**Themes**: Security hardening (error message suppression, path validation), performance (virtualization, selector granularity, memoization), cleanup (backward-compat re-exports, import paths).

**33 files changed** across 4 domains.

## 2. Files by Risk Domain

| Domain | Files | Risk |
|--------|-------|------|
| Audio DSP | `auralis/dsp/basic.py` | HIGH |
| Backend Routes | `auralis-web/backend/routers/enhancement.py`, `processing_api.py` | HIGH |
| Frontend Store | `auralis-web/frontend/src/store/slices/playerSlice.ts` | MEDIUM |
| Frontend Hooks | `useKeyboardShortcuts.ts`, `useLibraryData.ts`, `useLibraryWithStats.ts`, `useReduxState.ts` | MEDIUM |
| Frontend Components | `QueuePanel.tsx`, 12 settings files, 8 library files | LOW-MEDIUM |
| Frontend Services | `playlistService.ts` | LOW |
| Docs | `AUDIT_FRONTEND_2026-03-04.md` | LOW |

## 3. High-Risk Changes Review

### `auralis/dsp/basic.py` — normalize() silent audio copy

**Change**: `return audio` → `return audio.copy()` for the zero-peak branch.

**Verdict**: CORRECT. Fixes #2683. The silent audio path now returns an independent copy, consistent with the non-silent path which creates a new array via `audio * (target_level / peak)`. Audio invariants preserved: output is `np.ndarray`, `len(output) == len(input)`, no in-place mutation.

### `auralis-web/backend/routers/enhancement.py` — Error message suppression

**Change**: All `HTTPException(detail=f"... {e}")` replaced with static strings. `exc_info=True` added to logger calls. `PathValidationError` detail collapsed to generic message.

**Verdict**: CORRECT. Fixes #2666 and #2629. No raw exception messages leak to clients. Full tracebacks are logged server-side. No contract breaks — frontend only checks HTTP status codes, not error message content.

### `auralis-web/backend/routers/processing_api.py` — Same error message pattern

**Change**: Same pattern as enhancement.py — static error messages, `exc_info=True` logging.

**Verdict**: CORRECT. No issues found.

## 4. Findings

### INC-12: QueuePanel virtualization breaks native drag-and-drop for off-screen items
- **Severity**: MEDIUM
- **Changed File**: `auralis-web/frontend/src/components/player/QueuePanel.tsx` (commit: a5adfb72)
- **Status**: NEW
- **Description**: The QueuePanel was virtualized with `@tanstack/react-virtual` (overscan=5), but the drag-and-drop implementation uses native HTML5 `draggable`/`onDragOver` events. With virtualization, only visible items plus 5 overscan items exist in the DOM. When a user drags a track to a position beyond the rendered range (e.g., from position 3 to position 40 in a 50-track queue), the target `<li>` elements don't exist in the DOM, so `onDragOver` never fires and the drop target is unreachable. Additionally, `handleReorderTrack` fires continuously during drag (on every `onDragOver`), which means rapid reordering during drag interleaves with virtualizer's position calculations, potentially causing visual flicker.
- **Evidence**:
  ```tsx
  // Only rendered items receive drag events
  {virtualizer.getVirtualItems().map((virtualRow) => {
    return (
      <QueueTrackItem
        draggable
        onDragOver={(e) => {
          e.preventDefault();
          onDragOver(index);  // Cannot fire if item is not rendered
        }}
      />
    );
  })}
  ```
- **Impact**: Users with large queues (>15 tracks) cannot drag-reorder tracks to positions outside the visible viewport. The queue reorder feature becomes partially broken.
- **Suggested Fix**: Either (a) auto-scroll the container during drag using `onDragOver` on the container element to detect proximity to edges, or (b) replace native HTML5 drag-and-drop with a virtualization-aware library like `@dnd-kit` with its `SortableContext` that handles virtualized lists, or (c) increase overscan significantly for the drag-active state.

### INC-13: useKeyboardShortcuts useMemo receives unstable reference at both call sites
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts` (commit: 82c3eaaf)
- **Status**: NEW
- **Description**: The fix wraps `shortcutsToRegister` in `useMemo([configOrShortcuts])`, but both call sites pass unstable references:
  1. `ComfortableApp.tsx:277` passes `keyboardShortcutsArray`, an array literal created inline every render
  2. `useAppKeyboardShortcuts.ts:120` passes `unifiedConfig`, the return value of `adaptConfigToUnified(config)` which creates a new object every render

  Since `useMemo` uses `Object.is` comparison on deps, a new array/object reference every render means the memo never caches.
- **Evidence**:
  ```ts
  // useKeyboardShortcuts.ts — memo depends on object identity
  const shortcutsToRegister = useMemo(
    () => Array.isArray(configOrShortcuts)
      ? configOrShortcuts
      : configToServiceShortcuts(configOrShortcuts || {}),
    [configOrShortcuts]  // New object each render → memo always recomputes
  );
  ```
  ```tsx
  // ComfortableApp.tsx — array created inline
  const keyboardShortcutsArray = [ ... ];  // new array every render
  useKeyboardShortcuts(keyboardShortcutsArray);
  ```
- **Impact**: The `useMemo` provides no caching benefit. The downstream `useEffect([shortcutsToRegister])` still fires every render, calling `keyboardShortcuts.clear()` + `startListening()` repeatedly. This is the same behavior as before the fix. No functional breakage, but the performance optimization is ineffective.
- **Suggested Fix**: Either (a) move `keyboardShortcutsArray` into a `useMemo` at the call site, or (b) use `useRef` + deep comparison inside `useKeyboardShortcuts` to stabilize the value, or (c) accept a serializable config and memoize on `JSON.stringify(configOrShortcuts)`.

## 5. Cross-Layer Impact

All changes reviewed for cross-layer consistency:

- **Backend error messages → Frontend**: Frontend does not parse error message text (only checks HTTP status), so the change to static error messages is safe.
- **Track type re-exports removed → All consumers**: All 9 removed `export type Track = ...` aliases were replaced with direct imports from `@/types/domain`. Checked: `DraggableTrackRow.tsx` now imports `LibraryTrack as Track` from domain types, `useTrackContextMenu.ts` does the same. No broken imports.
- **playerSlice Track type → consumers**: The `Track` re-export from `playerSlice` was removed. Changed to `PlayerTrack` directly. Internal-only usage, no external consumers.
- **usePlaybackProgress refactor**: Changed from `usePlayerState()` (which subscribes to entire player slice) to two granular `useSelector` calls for `currentTime` and `duration`. Correct — reduces re-renders from ~20 fields to 2.

No cross-layer contract breaks detected.

## 6. Missing Tests

| Change | Test Coverage |
|--------|--------------|
| `normalize()` copy fix | Likely covered by existing DSP tests (validates return value, not identity) |
| Backend error message suppression | Tests should verify error responses don't contain exception text — not verified |
| QueuePanel virtualization | No test for drag-and-drop behavior with virtualized list |
| useKeyboardShortcuts memoization | Existing test suite doesn't test re-render behavior |
| usePlaybackProgress selectors | No dedicated test for selector granularity |
| Settings error state rendering | No test verifying error Alert is rendered on load failure |

## 7. Summary

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| INC-12 | MEDIUM | QueuePanel virtualization breaks native drag-and-drop for off-screen items | NEW |
| INC-13 | LOW | useKeyboardShortcuts useMemo receives unstable reference at both call sites | NEW |
