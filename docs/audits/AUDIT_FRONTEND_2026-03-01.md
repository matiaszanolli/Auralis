# Frontend Audit — 2026-03-01 (v4)

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: 3 parallel exploration agents (Hooks/Redux/Contexts, Components/Design/Services/A11y, Types/Perf/Tests/Config), followed by manual verification of all candidate findings against source code. Prior findings FE-11–FE-23 re-verified. 15+ false positives eliminated.

## Executive Summary

The settings panel overhaul (commit `d087caee`) introduced new code with several issues: raw `fetch()` bypassing the API client, unreported error state, a hardcoded color, and relative imports. The most significant finding across the codebase is **FE-24**: TypeScript 4.9.5 cannot parse `moduleResolution: "bundler"` (requires TS 5.0+), meaning `tsc --noEmit` fails immediately and **no type checking has been running**. All TypeScript types are decorative.

Five prior findings are now verified **FIXED** (FE-13, FE-16, FE-17, FE-20, FE-21, FE-22). Six prior findings remain open.

**Results**: 9 new confirmed findings (0 CRITICAL, 1 HIGH, 4 MEDIUM, 4 LOW). Total open findings after this pass: 15 (6 carried-over + 9 new).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 1 | 0 | 1 |
| MEDIUM | 4 | 4 | 8 |
| LOW | 4 | 2 | 6 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 178 console.log statements, no production stripping | #2597 | **STILL OPEN** — vite.config.mts has no `esbuild.drop` or `terser` config |
| FE-12: WebSocketContext propagates `any` instead of typed union | #2598 | **STILL OPEN** — `data?: any`, `current_track: any`, `send: (message: any)` unchanged |
| FE-13: Queue toggle button missing `aria-expanded` | #2599 | **FIXED** — commit `7a22efe0` |
| FE-14: 5 player components exceed 300-line guideline | #2600 | **STILL OPEN** — Player.tsx 549 lines, QueuePanel 654 lines, etc. |
| FE-15: No tests for usePlayEnhanced and AudioPlaybackEngine | #2601 | **FIXED** — `usePlayEnhanced.test.ts` (1,056 lines) covers full pipeline |
| FE-16: EnhancementContext silently swallows errors | #2602 | **FIXED** — all three methods now set error state and re-throw consistently |
| FE-17: useLibraryData loadMore stale `isLoadingMore` guard | #2603 | **FIXED** — ref-based guard `isLoadingMoreRef` with synchronous set |
| FE-18: usePlayNormal passes handlers directly to subscribe | #2604 | **STILL OPEN** — lines 443-458 still use direct handler pass |
| FE-19: Design system primitives use `{...(props as any)}` | #2605 | **STILL OPEN** — 6+ primitives unchanged |
| FE-20: 15+ components import from deprecated Color.styles.ts | #2617 | **FIXED** — Color.styles.ts deleted, all imports migrated to `@/design-system` |
| FE-21: BatchActionsMoreMenu hardcodes `color: 'white'` | #2618 | **FIXED** — now uses `tokens.colors.text.primaryFull` |
| FE-22: QueueStatisticsPanel mutable string key | #2619 | **FIXED** — now uses index-based keys |
| FE-23: AudioPlaybackEngine and index.tsx use `window as any` | #2620 | **STILL OPEN** — lines 25, 37, 95 unchanged |
| ArtworkResponse frontend type mismatch | #2627 | **STILL OPEN** |

## New Findings

---

### FE-24: TypeScript 4.9.5 incompatible with tsconfig `moduleResolution: "bundler"`
- **Severity**: HIGH
- **Dimension**: Type Safety
- **Location**: `auralis-web/frontend/package.json:28` and `auralis-web/frontend/tsconfig.json:10`
- **Status**: NEW
- **Description**: The `tsconfig.json` specifies `"moduleResolution": "bundler"` which requires TypeScript 5.0+. However, `package.json` declares `"typescript": "^4.9.5"` and the installed version is 4.9.5. Running `tsc --noEmit` fails immediately with `TS6046: Argument for '--moduleResolution' option must be: 'node', 'classic', 'node16', 'nodenext'`. This means **no type checking is being performed** — all TypeScript errors silently pass, rendering `"strict": true` and all typed interfaces ineffective.
- **Evidence**:
  ```json
  // tsconfig.json:10
  "moduleResolution": "bundler",

  // package.json:28
  "typescript": "^4.9.5",
  ```
  ```
  $ npx tsc --noEmit
  tsconfig.json(10,25): error TS6046: Argument for '--moduleResolution' option
  must be: 'node', 'classic', 'node16', 'nodenext'.
  ```
- **Impact**: Every TypeScript type definition in the codebase is decorative only. Missing imports, wrong `as` casts, type mismatches — none are caught at compile time. This is the root enabler for multiple `as any` casts persisting uncaught (FE-12, FE-19, FE-23, #2627).
- **Suggested Fix**: Upgrade TypeScript to `^5.5.0` or later in `package.json` and run `npm install`. Then run `tsc --noEmit` and fix the resulting type errors. Alternatively, change `moduleResolution` to `"node"` if staying on TS 4.x.

---

### FE-25: EnhancementContext shared `isProcessing` flag races between concurrent API calls
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/EnhancementContext.tsx:76-183`
- **Status**: NEW
- **Description**: All three mutation methods (`setEnabled`, `setPreset`, `setIntensity`) share a single `isProcessing` boolean state. There is no guard preventing concurrent calls. If a user toggles enable and then immediately changes the preset, the sequence is:
  1. `setEnabled(true)` → sets `isProcessing = true`
  2. `setPreset('warm')` → sets `isProcessing = true` (already true, no guard)
  3. `setEnabled` completes → sets `isProcessing = false` in `finally`
  4. UI now shows `isProcessing = false` while `setPreset` is still in-flight
- **Evidence**:
  ```typescript
  // setEnabled, line 111-113:
  } finally {
    setIsProcessing(false);  // Clears flag even if setPreset is still running
  }

  // setPreset, line 144-146:
  } finally {
    setIsProcessing(false);  // Also clears flag unconditionally
  }
  ```
- **Impact**: UI loading/disabled state becomes inconsistent when two enhancement operations overlap. The spinner stops prematurely for one operation. No data corruption — each API call still completes independently.
- **Suggested Fix**: Replace the single boolean with a counter: `const [processingCount, setProcessingCount] = useState(0)`. Set `isProcessing = processingCount > 0`. Each method increments on entry and decrements in `finally`.

---

### FE-26: `triggerLibraryScan` bypasses centralized API client with unchecked raw fetch
- **Severity**: MEDIUM
- **Dimension**: API Client & Data Fetching
- **Location**: `auralis-web/frontend/src/services/settingsService.ts:136-142`
- **Status**: NEW
- **Description**: The `triggerLibraryScan` function uses raw `fetch()` instead of the project's centralized `apiRequest` utility. It does not check `response.ok`, does not parse error responses, and does not use `getApiUrl()` for URL construction. HTTP 4xx/5xx errors are silently ignored — the function resolves successfully even when the backend rejects the request. Note that `fetch()` only rejects on network failure, not on HTTP errors.
- **Evidence**:
  ```typescript
  // settingsService.ts:136-142
  export async function triggerLibraryScan(directories: string[]): Promise<void> {
    await fetch('/api/library/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directories, recursive: true, skip_existing: true }),
    });
    // No response.ok check — 4xx/5xx silently succeeds
  }
  ```
  Compare with all other functions in the same file which use `crudService` (backed by `apiRequest`).
- **Impact**: When a scan trigger fails (e.g., 422 invalid path, 500 server error), `handleScanNow` catches exceptions but `triggerLibraryScan` never throws on HTTP errors. The user sees no error feedback.
- **Suggested Fix**: Use the project's `apiRequest` utility or at minimum check `response.ok` and throw on failure.

---

### FE-27: `useSettingsDialog.error` state is never rendered in SettingsDialog UI
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/settings/useSettingsDialog.ts:25,170-175` and `auralis-web/frontend/src/components/settings/SettingsDialog.tsx:34-47`
- **Status**: NEW
- **Description**: The `useSettingsDialog` hook maintains an `error` state (line 25) that is set on failure of load, save, reset, add folder, remove folder, and scan operations (6 error paths). It is returned from the hook (line 175). However, `SettingsDialog.tsx` does **not** destructure `error` from the hook (lines 34-47), and no settings component renders it.
- **Evidence**:
  ```typescript
  // useSettingsDialog.ts returns error:
  return { settings, loading, pendingChanges, isSaving, error, ... };

  // SettingsDialog.tsx destructures WITHOUT error:
  const {
    loading,
    isSaving,
    removeConfirmFolder,
    handleSettingChange,
    handleSave,
    // ... no 'error' here
  } = useSettingsDialog({ open, onSettingsChange });
  ```
- **Impact**: When settings operations fail, the user gets no visual feedback. The dialog either stays loading forever (load failure), appears to succeed (save failure), or silently fails (folder/scan operations).
- **Suggested Fix**: Destructure `error` from the hook in `SettingsDialog.tsx` and render an `<Alert severity="error">` at the top of the dialog content when `error` is non-null.

---

### FE-28: `queueSlice.setQueue([])` sets `currentIndex` to `-1`
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts:134-143`
- **Status**: NEW
- **Description**: The `setQueue` reducer computes `state.currentIndex = Math.min(state.currentIndex, state.tracks.length - 1)`. When the payload is an empty array, `tracks.length - 1 = -1`, resulting in `currentIndex = -1`. This is an invalid index. Compare with `clearQueue` (line 120-128) which correctly resets `currentIndex = 0`.
- **Evidence**:
  ```typescript
  // queueSlice.ts:134-138 — setQueue
  setQueue: {
    reducer(state, action: PayloadAction<Track[], string, { timestamp: number }>) {
      state.tracks = action.payload;
      state.currentIndex = Math.min(state.currentIndex, state.tracks.length - 1);
      //                                                  -1 when tracks is empty
    },
  },

  // queueSlice.ts:120-124 — clearQueue (correct)
  clearQueue: {
    reducer(state) {
      state.tracks = [];
      state.currentIndex = 0;  // ← correct
    },
  },
  ```
- **Impact**: After a `queue_updated` WebSocket message with an empty array, `currentIndex` becomes `-1`. Selectors reading `tracks[currentIndex]` return `undefined`. Code checking `currentIndex > 0` for "has previous track" will behave incorrectly.
- **Suggested Fix**: Add `Math.max(0, ...)` guard: `state.currentIndex = Math.max(0, Math.min(state.currentIndex, state.tracks.length - 1))`.

---

### FE-29: SettingsDialogHeader hardcodes `color: 'white'` bypassing design tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: `auralis-web/frontend/src/components/settings/SettingsDialogHeader.tsx:23`
- **Status**: NEW
- **Description**: The close button uses `sx={{ color: 'white' }}` — a hardcoded CSS color. The file already imports `IconButton` from `@/design-system` but does not import `tokens`. This is the same class of issue as FE-21 (fixed in this cycle).
- **Evidence**:
  ```tsx
  // SettingsDialogHeader.tsx:23
  <IconButton onClick={onClose} sx={{ color: 'white' }}>
  //                                       ^^^^^^^^^^^^^ hardcoded
  ```
- **Impact**: Color does not adapt to theme changes. Inconsistent with the rest of the codebase.
- **Suggested Fix**: Change to `sx={{ color: tokens.colors.text.primaryFull }}` and add `import { tokens } from '@/design-system'`.

---

### FE-30: ScanStatusCard lacks `aria-live` region for screen reader scan updates
- **Severity**: LOW
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:55-157`
- **Status**: NEW
- **Description**: ScanStatusCard transitions between scanning/idle states and shows live progress (file count, percentage, current file), but the container has no `aria-live` or `role="status"` attribute. MUI's `LinearProgress` has `role="progressbar"`, but surrounding status text ("Scanning…", "3 / 15", "+5 added") is not announced.
- **Evidence**:
  ```tsx
  // ScanStatusCard.tsx:55-61 — outer Box missing aria-live
  <Box sx={{
    ...tokens.glass.subtle,
    borderRadius: tokens.borderRadius.sm,
    overflow: 'hidden',
    // ← No aria-live, no role="status"
  }}>
  ```
- **Impact**: Screen reader users are not informed of scan progress or completion unless they manually re-focus the component.
- **Suggested Fix**: Add `aria-live="polite"` and `role="status"` to the outer `<Box>`.

---

### FE-31: Settings components use relative imports instead of `@/` absolute paths
- **Severity**: LOW
- **Dimension**: Design System (import conventions)
- **Location**: `auralis-web/frontend/src/components/settings/ScanStatusCard.tsx:22`, `SettingsDialog.tsx:11,19`, `useSettingsDialog.ts:2`
- **Status**: NEW
- **Description**: The new settings components use relative imports (`../../hooks/library/useScanProgress`, `../../services/settingsService`) instead of the `@/` absolute import convention required by CLAUDE.md. `ScanStatusCard.tsx` is a new file that should follow the convention from creation.
- **Evidence**:
  ```typescript
  // ScanStatusCard.tsx:22
  import { useScanProgress } from '../../hooks/library/useScanProgress';

  // SettingsDialog.tsx:11
  import { UserSettings } from '../../services/settingsService';

  // useSettingsDialog.ts:2
  import { settingsService, UserSettings, SettingsUpdate } from '../../services/settingsService';
  ```
- **Impact**: Violates project import convention. Relative paths create brittle directory-structure dependencies. Inconsistent with `@/design-system` imports in the same files.
- **Suggested Fix**: Replace `../../hooks/` with `@/hooks/` and `../../services/` with `@/services/` across the settings directory.

---

### FE-32: Six unused production dependencies inflate install size
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/package.json:6-31`
- **Status**: NEW
- **Description**: Six production dependencies declared in `package.json` have zero imports in any source file: `tone` (~875KB), `wavesurfer.js` (~150KB), `web-vitals` (~3KB), `react-dropzone` (~25KB), `axios` (~45KB), and `framer-motion` (~150KB). Vite's tree-shaking excludes them from the bundle, but they inflate `npm install` time and `node_modules` size (~1.25MB combined).
- **Evidence**:
  ```bash
  # Zero imports found for any of these packages:
  grep -rn "from ['\"]tone" src/                 # (no results)
  grep -rn "from ['\"]wavesurfer" src/           # (no results)
  grep -rn "from ['\"]web-vitals" src/           # (no results)
  grep -rn "from ['\"]react-dropzone" src/       # (no results)
  grep -rn "from ['\"]axios" src/                # (no results)
  grep -rn "from ['\"]framer-motion" src/        # (no results)
  ```
- **Impact**: Unnecessary install time, larger `node_modules`, risk of accidental inclusion if any transitive code references them.
- **Suggested Fix**: Remove these six packages from `dependencies`. Re-add when actually used.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `PlayerStateData` camelCase/snake_case mismatch causes `as any` | Documented intentional design: comment at websocket.ts:71-76 explains the mapping pattern. The `as any` casts in consumption hooks are explicit, with clear snake→camel mapping. |
| `ALL_MESSAGE_TYPES` missing 6 streaming types | Audio streaming types (`audio_stream_start`, `audio_chunk`, etc.) are deliberately omitted from the "all" array — they are high-frequency binary messages subscribed to individually via dedicated handlers, not via bulk subscription. |
| `STATUS_UPDATE` handler dispatches 6 individual actions | All dispatches are synchronous within one WebSocket handler. React 18 automatic batching coalesces these into a single render. No intermediate state is observable by React components. |
| Duplicate `useScanProgress` subscriptions in SettingsDialog tree | `SettingsDialog` uses `isScanning` (one field) and `ScanStatusCard` uses the full state. While both subscribe independently, `useWebSocketSubscription` manages its lifecycle correctly and the overhead is negligible (4 message types × 2 subscriptions). |
| `handleSave` callback identity changes on every keystroke | `pendingChanges` is a dependency of `handleSave` via `useCallback`. `SettingsDialogFooter` is not memoized, so re-renders are expected regardless. No observable performance impact in a settings dialog. |
| `loadSettings` missing from `useEffect` dependency array | `loadSettings` is a `useCallback` with `[]` deps — the reference is stable and never changes. While a lint warning, it's not a bug. |
| `performance.memory` accessed via `as any` in performance monitors | Non-standard Chrome-only API. The `as any` cast is the pragmatic correct approach; no standard typing exists. |
| `(window as any).webkitAudioContext` in player hooks | Standard Safari compatibility pattern for Web Audio API. No better typing exists for the prefixed variant. |
| `AuroraWaveIcon.tsx` uses `stroke="white"` | SVG attribute, not a CSS color. SVG attributes cannot reference JS tokens. Inherent to inline SVGs. |
| `serviceFactory.ts` uses `any` for generic defaults | Pre-existing design pattern across the codebase (not introduced by recent changes). The factory is consumed by 5 services. While imperfect, this is a systemic issue not a new finding. |
| `QueueRecommendationsPanel` uses `any` for track types | Pre-existing, not introduced by recent changes. Already tracked under the general `as any` concerns. |

## Dimension Checklist Summary

### Dimension 1: Component Quality
- [x] Single responsibility — hooks handle logic, components handle rendering
- [ ] **Size guideline** — FE-14 (5 player components + AlbumCharacterPane exceed 300 lines, open #2600)
- [x] Key stability — all lists use stable keys (FE-22 FIXED)
- [x] Error boundaries — ErrorBoundary wraps `<App />` at root
- [ ] **Error display** — FE-27 (useSettingsDialog.error never rendered)

### Dimension 2: Redux State Management
- [x] Normalized state — no duplication between slices
- [x] Selector memoization — comprehensive `createSelector` usage
- [ ] **Edge case** — FE-28 (setQueue([]) creates invalid -1 index)
- [x] Async error handling — thunks dispatch error states
- [x] Serializable state — no functions or class instances in Redux

### Dimension 3: Hook Correctness
- [x] useLibraryData loadMore race — FIXED (#2603)
- [x] EnhancementContext error handling — FIXED (#2602)
- [ ] **EnhancementContext isProcessing** — FE-25 (shared flag races between concurrent calls)
- [ ] **usePlayNormal handler subscriptions** — FE-18 (open #2604)
- [x] useEffect cleanup — WebSocket, timers, AbortControllers all properly cleaned up

### Dimension 4: TypeScript Type Safety
- [ ] **TypeScript version** — FE-24 (4.9.5 cannot parse `moduleResolution: "bundler"`, tsc fails)
- [ ] **WebSocketContext `any`** — FE-12 (open #2598)
- [ ] **Design system primitives `as any`** — FE-19 (open #2605)
- [ ] **`window as any`** — FE-23 (open #2620)
- [x] Domain types — camelCase interfaces with documented snake_case mapping

### Dimension 5: Design System Adherence
- [x] Color.styles.ts migration — FIXED (FE-20, file deleted)
- [x] BatchActionsMoreMenu — FIXED (FE-21)
- [ ] **Hardcoded `color: 'white'`** — FE-29 (SettingsDialogHeader)
- [ ] **Relative imports** — FE-31 (settings components use `../../` instead of `@/`)
- [x] All other components use `@/design-system` tokens

### Dimension 6: API Client & Data Fetching
- [x] EnhancementContext errors — FIXED (#2602)
- [ ] **Raw fetch** — FE-26 (triggerLibraryScan bypasses apiRequest, no error checking)
- [x] AbortController cleanup — per-request + unmount cleanup intact
- [x] Transformer layer — per-entity snake→camel transformers

### Dimension 7: Performance
- [ ] **Console logging in production** — FE-11 (open #2597)
- [ ] **Unused dependencies** — FE-32 (6 packages with zero imports)
- [x] List virtualization, position updates, bundle splitting — all intact

### Dimension 8: Accessibility
- [x] Queue toggle `aria-expanded` — FIXED (#2599)
- [ ] **Scan progress** — FE-30 (ScanStatusCard missing aria-live)
- [x] ProgressBar ARIA, keyboard nav, live region — all intact

### Dimension 9: Test Coverage
- [x] `usePlayEnhanced` — FIXED (#2601), 1,056-line test file
- [x] Player hooks, selectors, integration tests — all intact
- [x] No snapshot tests — proper assertion-based testing
