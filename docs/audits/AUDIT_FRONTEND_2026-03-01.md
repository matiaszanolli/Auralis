# Frontend Audit — 2026-03-01 (v3)

**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: 3 parallel exploration agents (Hooks/Redux/Services, Components/Design/A11y, Config/Types/Tests), followed by manual verification of all candidate findings against source. Prior findings FE-11–FE-19 re-verified. 7 false positives from agents eliminated.

## Executive Summary

The codebase continues to mature. `usePlayEnhanced` now has a 1,056-line test suite (FE-15 **FIXED**). The `useLibraryData` loadMore race condition is **FIXED** (#2603). Queue toggle `aria-expanded` is **FIXED** (#2599). All other open prior findings remain unchanged.

**Results**: 4 new confirmed findings (0 CRITICAL, 0 HIGH, 1 MEDIUM, 3 LOW). Total open findings after this pass: 10 (6 carried-over + 4 new).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 1 | 4 | 5 |
| LOW | 3 | 2 | 5 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 178 console.log statements, no production stripping | #2597 | **STILL OPEN** — vite.config.mts has no `esbuild.drop` or `terser` config |
| FE-12: WebSocketContext propagates `any` instead of typed discriminated union | #2598 | **STILL OPEN** — `data?: any`, `current_track: any`, `send: (message: any)` unchanged |
| FE-13: Queue toggle button missing `aria-expanded` | #2599 | **FIXED** — commit `7a22efe0` adds `aria-expanded={queuePanelOpen}` to Player.tsx |
| FE-14: 5 player components exceed 300-line guideline | #2600 | **STILL OPEN** — Player.tsx now 549 lines (+1 for aria-expanded fix), others unchanged |
| FE-15: No tests for usePlayEnhanced and AudioPlaybackEngine | #2601 | **FIXED** — `usePlayEnhanced.test.ts` (1,056 lines) covers full PCM streaming pipeline |
| FE-16: EnhancementContext silently swallows errors, unvalidated response | #2602 | **STILL OPEN** — setPreset/setIntensity catch blocks unchanged (no re-throw, no error state) |
| FE-17: useLibraryData loadMore stale `isLoadingMore` guard | #2603 | **FIXED** — commit `7a22efe0` replaces state guard with `isLoadingMoreRef` |
| FE-18: usePlayNormal passes handlers directly to subscribe, not via refs | #2604 | **STILL OPEN** — lines 443-458 still use direct handler pass with `as any` cast |
| FE-19: Design system primitives use `{...(props as any)}` | #2605 | **STILL OPEN** — 6 primitives unchanged (Card, Slider, IconButton, Button, Badge, Input) |
| #2606: No player state push on WebSocket reconnect | #2606 | **STILL OPEN** — WebSocketContext reconnect path still doesn't re-send current state |

## New Findings

---

### FE-20: 15+ components import from deprecated `Color.styles.ts` via relative paths
- **Severity**: MEDIUM
- **Dimension**: Design System
- **Location**: Multiple files (see evidence)
- **Status**: NEW
- **Description**: `components/library/Styles/Color.styles.ts` is an explicit compatibility shim with a `@deprecated` JSDoc on every export, instructing users to import directly from `@/design-system`. Despite this, 15+ files across the codebase still import from this file using relative paths, violating two project rules simultaneously: the `@/` absolute import requirement (CLAUDE.md) and the direct design-system token usage guideline.
- **Evidence**:
  ```typescript
  // Color.styles.ts — top-level deprecation notice:
  /**
   * @deprecated This file is deprecated. Import directly from '@/design-system' instead.
   * Migration guide:
   *   auroraOpacity → tokens.colors.opacityScale.accent
   *   gradients/gradientPresets → tokens.gradients.decorative
   */
  ```
  Files still importing via relative path (all should migrate to `@/design-system`):
  ```
  AppEnhancementPaneHeader.tsx:12  import { auroraOpacity } from '../../library/Styles/Color.styles'
  AppEnhancementPaneFooter.tsx:10  import { auroraOpacity } from '../../library/Styles/Color.styles'
  DebugInfo.tsx:3                  import { auroraOpacity, colorAuroraPrimary } from '../library/Styles/Color.styles'
  AuroraLogo.styles.ts:6           import { gradients, auroraOpacity } from '../library/Styles/Color.styles'
  SearchBar.styles.ts:5            import { auroraOpacity } from '../library/Styles/Color.styles'
  ViewToggle.tsx:4                 import { gradients, auroraOpacity } from '../library/Styles/Color.styles'
  SettingsDialog.styles.ts:3       import { auroraOpacity } from '../library/Styles/Color.styles'
  FoldersList.tsx:14               import { auroraOpacity } from '../library/Styles/Color.styles'
  AppTopBarLeftSection.tsx:4       import { auroraOpacity } from '../library/Styles/Color.styles'
  AppMainContent.tsx:3             import { auroraOpacity } from '../library/Styles/Color.styles'
  AppTopBarSearchInput.tsx:5       import { auroraOpacity } from '../library/Styles/Color.styles'
  BatchActionsMoreMenu.tsx:11      import { auroraOpacity } from '../Styles/Color.styles'
  AudioCharacteristics.tsx:~15     import { auroraOpacity } from '../../../library/Styles/Color.styles'
  (and others in enhancement-pane/sections/)
  ```
- **Impact**: Every relative import to a deprecated file adds drift risk — the compatibility layer exists only for migration and may be removed without warning. Relative `../` paths create brittle dependency on directory structure. The migration path is fully documented in the file itself but not being followed.
- **Suggested Fix**: Migrate all import sites to use `@/design-system` tokens directly per the migration guide in `Color.styles.ts`. For example: `auroraOpacity.standard` → `tokens.colors.opacityScale.accent.standard`. After all sites are migrated, remove `Color.styles.ts`.

---

### FE-21: `BatchActionsMoreMenu.tsx:51` hardcodes `color: 'white'` bypassing design tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/library/Controls/BatchActionsMoreMenu.tsx:51`
- **Status**: NEW
- **Description**: The `MenuItem` uses `sx={{ color: 'white', gap: 1 }}` — a hardcoded CSS color string that bypasses the design system token infrastructure. The file already imports `tokens` from `@/design-system`, making this an isolated omission.
- **Evidence**:
  ```tsx
  // BatchActionsMoreMenu.tsx:51
  <MenuItem onClick={handleEditClick} sx={{ color: 'white', gap: 1 }}>
  //                                         ^^^^^^^^^^^^^ hardcoded
  ```
  The design system has `tokens.colors.text.primaryFull` (white at full opacity) for this case.
- **Impact**: Text color does not adapt to theme changes or future palette updates. Minor visual regression risk if the background color changes.
- **Suggested Fix**: Replace `'white'` with `tokens.colors.text.primaryFull`.

---

### FE-22: `QueueStatisticsPanel.tsx:282` uses mutable string content as React list key
- **Severity**: LOW
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/QueueStatisticsPanel.tsx:282`
- **Status**: NEW
- **Description**: Quality assessment issues are rendered with `key={\`issue-${issue}\`}` where `issue` is the string content of the issue message. If two assessment issues have identical text (e.g., "Low dynamic range" appearing twice), React will emit a duplicate key warning and reconciliation may silently drop one item.
- **Evidence**:
  ```tsx
  // QueueStatisticsPanel.tsx:281-285
  {assessment.issues.map((issue) => (
    <div key={`issue-${issue}`} style={styles.issueItem}>
    //          ^^^^^ string content as key — collision if duplicate issues
      • {issue}
    </div>
  ))}
  ```
  The `assessment.issues` array is produced by the quality assessment algorithm; the uniqueness of issue strings is not guaranteed.
- **Impact**: In the unlikely case of duplicate issue strings, one entry is silently dropped from the rendered list. React also emits a console warning.
- **Suggested Fix**: Use `key={`issue-${index}`}` (index is stable for a static non-reorderable list of issues).

---

### FE-23: `AudioPlaybackEngine.ts` and `index.tsx` use `window as any` for global property access
- **Severity**: LOW
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts:25,37,95`; `auralis-web/frontend/src/index.tsx:29`
- **Status**: NEW
- **Description**: Four sites attach properties to `window` using `(window as any).__auralisXxx`:
  ```typescript
  // AudioPlaybackEngine.ts:25 — read
  const existing = (window as any).__auralisAnalyser as AnalyserNode | undefined;

  // AudioPlaybackEngine.ts:37,95 — write
  (window as any).__auralisAnalyser = analyser;
  (window as any).__auralisAudioContext = audioContext;

  // index.tsx:29 — write
  (window as any).__AURALIS_DEBUG__ = { commitId, buildMode, version };
  ```
  TypeScript's strict mode is enabled (`"strict": true` in tsconfig.json). The `as any` cast disables all type checking on the read/write. Accessing a non-existent property on `window as any` returns `undefined` silently rather than a compile-time error.
- **Impact**: Typos in property names (e.g., `__auralisAnalyser` vs `__auralisAnalyzer`) are not caught at compile time. Downstream consumers that read these globals must also cast to `any`, propagating the type hole.
- **Suggested Fix**: Add a `declare global` interface extension:
  ```typescript
  declare global {
    interface Window {
      __auralisAnalyser?: AnalyserNode;
      __auralisAudioContext?: AudioContext;
      __AURALIS_DEBUG__?: { commitId: string; buildMode: string; version: string };
    }
  }
  ```

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `useOptimisticUpdate` stale closure over `options.onSuccess/onError` | `options` is in the `execute` dependency array; the callback is recreated when options changes, so it always captures the latest callbacks. No stale closure. |
| `AudioPlaybackEngine.feedInterval` memory leak on component unmount | `stopPlayback()` (line 209) → `disconnectProcessor()` (line 306) → `stopFeeding()` (line 430) clears the interval. `usePlayEnhanced` has a `useEffect` cleanup at line 810 that calls `stopPlayback()` on unmount. |
| `AudioPlaybackEngine.samplesPlayed` race condition from worklet messages | JavaScript is single-threaded. `workletNode.port.onmessage` fires on the main thread event loop — there is no concurrent access to `this.samplesPlayed`. |
| WebSocket offline queue concurrent processing without guard | `processOfflineQueue` empties the queue synchronously (dequeue each message) before awaiting sends. Even if called twice, the second call finds an empty queue and exits. |
| `WS_BASE_URL = 'ws://localhost:8765'` mixed-content vulnerability | Confirmed correct for this Electron app architecture. Auralis always runs on localhost; mixed-content policy does not apply. Already documented in MEMORY.md. |
| `useFingerprintCache` concurrent preprocess state collisions | `simulateFingerprinting` uses an `AbortSignal` parameter; on abort, the `setProgress`/`setFingerprint` calls are guarded by `signal.aborted` checks (lines 125, 140). Concurrent calls correctly abort the prior simulation. |
| Relative import `../../../shared/ContextMenu` in `TrackRow.tsx` | This is within the same `components/` tree. Per project convention, cross-subtree imports use `@/`; intra-component relative paths are acceptable when within the same functional area. Verified this is a library-local import. |

## Dimension Checklist Summary

### Dimension 1: Component Quality
- [x] Single responsibility — hooks handle logic, components handle rendering
- [ ] **Size guideline** — FE-14 (5 player components + AlbumCharacterPane exceed 300 lines, open #2600)
- [x] Key stability — most lists use stable IDs
- [ ] **Mutable content key** — FE-22 (`QueueStatisticsPanel` issue strings as keys)
- [x] Error boundaries — ErrorBoundary wraps `<App />` at root

### Dimension 2: Redux State Management
- [x] All items — no new findings

### Dimension 3: Hook Correctness
- [ ] **usePlayNormal handler subscriptions** — FE-18 (open #2604, direct pass without ref indirection)
- [x] usePlayEnhanced — fully tested (FE-15 FIXED)
- [x] useLibraryData loadMore race — FIXED (#2603)

### Dimension 4: TypeScript Type Safety
- [ ] **WebSocketContext `any`** — FE-12 (open #2598)
- [ ] **Design system primitives `as any`** — FE-19 (open #2605)
- [ ] **`window as any`** — FE-23 (new, AudioPlaybackEngine + index.tsx)
- [x] Domain types — camelCase interfaces, transformer layer intact

### Dimension 5: Design System Adherence
- [ ] **Deprecated Color.styles.ts** — FE-20 (15+ components still importing via relative paths)
- [ ] **Hardcoded `color: 'white'`** — FE-21 (BatchActionsMoreMenu)
- [x] All other components use `@/design-system` tokens directly

### Dimension 6: API Client & Data Fetching
- [ ] **EnhancementContext error handling** — FE-16 (open #2602, setPreset/setIntensity swallow errors)
- [x] AbortController cleanup — per-request + unmount cleanup intact

### Dimension 7: Performance
- [ ] **Console logging in production** — FE-11 (open #2597, no vite build stripping)
- [x] List virtualization, position updates, bundle splitting — all intact

### Dimension 8: Accessibility
- [x] Queue toggle `aria-expanded` — FIXED (#2599)
- [x] All other a11y items verified intact

### Dimension 9: Test Coverage
- [x] `usePlayEnhanced` — FIXED (#2601), 1,056-line test file added
- [x] All other coverage items verified intact
