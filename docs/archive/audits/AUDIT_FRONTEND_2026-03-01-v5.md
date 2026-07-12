# Frontend Audit — 2026-03-01 (v5)

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality · Redux State · Hook Correctness · TypeScript · Design System · API Client · Performance · Accessibility · Test Coverage
**Method**: 3 parallel exploration agents (Hooks/Redux/Contexts, Components/Design/Services, Types/Perf/A11y/Tests), followed by manual verification of all candidate findings against source code. 15+ false positives eliminated. Prior findings FE-11–FE-32 and #2627 re-verified.
**Key Change Since v4**: TypeScript upgraded from 4.9.5 → 5.9.3 (commit `592891db`), fixing 899 type errors. FE-24 is resolved.

## Executive Summary

The TypeScript 5.x upgrade (FE-24) is now **FIXED** — `tsc --noEmit` works and strict mode is enforced. This was the most impactful fix since it enables all type checking. However, the codebase still has 440 `as any` casts across 85 files (production + test), and 412 console statements across 86 files ship to production.

Six new findings identified in this pass: a ThemeContext performance issue causing unnecessary re-renders, a SimilarityVisualization component with no async cleanup, EnhancementContext bypassing the centralized API client, a Redux reducer with a misleading `{...null}` spread, hardcoded colors in 4 files, and Vite loader console calls that can't be tree-shaken.

**Results**: 6 new confirmed findings (0 CRITICAL, 0 HIGH, 3 MEDIUM, 3 LOW). Total open findings after this pass: 20 (14 carried-over + 6 new).

| Severity | New | Carried-over (open) | Total Open |
|----------|-----|---------------------|------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 1 | 1 |
| MEDIUM | 3 | 7 | 10 |
| LOW | 3 | 6 | 9 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| FE-11: 412 console.log statements, no production stripping | #2597 | **STILL OPEN** — 412 occurrences across 86 files, vite.config.mts has no `esbuild.drop` config |
| FE-12: WebSocketContext propagates `any` instead of typed union | #2598 | **STILL OPEN** — `messageQueueRef = useRef<any[]>([])`, subscribe callback accepts `any` |
| FE-14: 5 player components exceed 300-line guideline | #2600 | **STILL OPEN** — Player.tsx 549 lines, QueuePanel 654 lines |
| FE-18: usePlayNormal passes handlers directly to subscribe | #2604 | **STILL OPEN** — lines 443-458 still cast `handleStreamStart as any` etc. |
| FE-19: Design system primitives use `{...(props as any)}` | #2605 | **STILL OPEN** — 8+ primitives (Box, Button, Card, Badge, etc.) |
| FE-23: AudioPlaybackEngine and index.tsx use `window as any` | #2620 | **STILL OPEN** — lines 25, 37, 93 of AudioPlaybackEngine.ts |
| FE-24: TypeScript 4.9.5 incompatible with tsconfig `moduleResolution: "bundler"` | #2632 | **FIXED** — TypeScript upgraded to 5.9.3, 899 type errors resolved (commit `592891db`) |
| FE-25: EnhancementContext shared `isProcessing` flag races | #2633 | **STILL OPEN** — single boolean shared by 3 async methods |
| FE-26: `triggerLibraryScan` bypasses API client with raw fetch | #2634 | **STILL OPEN** — settingsService.ts:136-142 unchanged |
| FE-27: `useSettingsDialog.error` state never rendered | #2635 | **STILL OPEN** — SettingsDialog.tsx:34-47 still doesn't destructure `error` |
| FE-28: `queueSlice.setQueue([])` sets `currentIndex` to `-1` | #2636 | **STILL OPEN** — queueSlice.ts:137 unchanged |
| FE-29: SettingsDialogHeader hardcodes `color: 'white'` | #2637 | **STILL OPEN** — SettingsDialogHeader.tsx:23 unchanged |
| FE-30: ScanStatusCard lacks `aria-live` region | #2638 | **STILL OPEN** — ScanStatusCard.tsx outer Box unchanged |
| FE-31: Settings components use relative imports | #2639 | **STILL OPEN** — SettingsDialog.tsx:11,12,19 unchanged |
| FE-32: Six unused production dependencies | #2640 | **STILL OPEN** — tone, wavesurfer.js, web-vitals, react-dropzone, axios, framer-motion |
| ArtworkResponse frontend type mismatch | #2627 | **STILL OPEN** — `artwork_path` vs `artwork_url` discrepancy |

## New Findings

---

### FE-33: ThemeContext provider value not memoized — cascading re-renders
- **Severity**: MEDIUM
- **Dimension**: Performance / Hook Correctness
- **Location**: `auralis-web/frontend/src/contexts/ThemeContext.tsx:58-72`
- **Status**: NEW → #2641
- **Description**: The `ThemeProvider` creates its context value object inline without `useMemo`, and defines `toggleTheme` and `setTheme` as inline arrow functions without `useCallback`. Every time the provider re-renders (including when its parent re-renders), a new value object with new function references is created, causing ALL `useTheme()` consumers to re-render even when theme state hasn't changed.
- **Evidence**:
  ```typescript
  // ThemeContext.tsx:58-72 — functions NOT wrapped in useCallback
  const toggleTheme = () => {
    setMode((prevMode) => (prevMode === 'dark' ? 'light' : 'dark'));
  };

  const setTheme = (newMode: ThemeMode) => {
    setMode(newMode);
  };

  // Value object NOT wrapped in useMemo
  const value = {
    mode,
    toggleTheme,  // ← new function reference every render
    setTheme,     // ← new function reference every render
    colors,
    glassEffects,
  };

  return (
    <ThemeContext.Provider value={value}> {/* new ref → all consumers re-render */}
  ```
- **Impact**: Any re-render of a component above `ThemeProvider` causes every component using `useTheme()` to re-render. This includes Player, QueuePanel, library views, and all styled components. While each individual re-render is cheap, the cascade affects the entire component tree.
- **Suggested Fix**: Wrap `toggleTheme` and `setTheme` in `useCallback`, then wrap the value object in `useMemo`:
  ```typescript
  const toggleTheme = useCallback(() => {
    setMode(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  const setTheme = useCallback((newMode: ThemeMode) => {
    setMode(newMode);
  }, []);

  const value = useMemo(() => ({
    mode, toggleTheme, setTheme, colors, glassEffects,
  }), [mode, toggleTheme, setTheme, colors, glassEffects]);
  ```

---

### FE-34: SimilarityVisualization async effect has no abort cleanup or mount guard
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `auralis-web/frontend/src/components/features/discovery/SimilarityVisualization.tsx:45-70`
- **Status**: NEW → #2645
- **Description**: The `useEffect` at line 45 calls `loadExplanation()` when track IDs change, but `loadExplanation` performs an async API call without an AbortController and without checking mount state before calling `setState`. If a user navigates away or the track IDs change rapidly, the earlier promise can resolve and update state with stale data.
- **Evidence**:
  ```typescript
  // SimilarityVisualization.tsx:44-70
  useEffect(() => {
    if (!trackId1 || !trackId2) {
      setExplanation(null);
      return;
    }
    loadExplanation();
    // ← No cleanup function returned, no AbortController
  }, [trackId1, trackId2, topN]);

  const loadExplanation = async () => {
    if (!trackId1 || !trackId2) return;
    setLoading(true);
    setError(null);
    try {
      const result = await similarityService.explainSimilarity(trackId1, trackId2, topN);
      setExplanation(result);  // ← Can set stale data if IDs changed during request
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load explanation');
    } finally {
      setLoading(false);
    }
  };
  ```
  Compare with `AlbumCharacterPane.tsx` which correctly uses `mountedRef` guard.
- **Impact**: If track IDs change rapidly (e.g., navigating through a list), stale similarity data from a previous pair can overwrite the correct data for the current pair. Also triggers React dev-mode warnings about unmounted component updates.
- **Suggested Fix**: Add a cleanup flag or AbortController:
  ```typescript
  useEffect(() => {
    if (!trackId1 || !trackId2) { setExplanation(null); return; }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await similarityService.explainSimilarity(trackId1, trackId2, topN);
        if (!cancelled) setExplanation(result);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [trackId1, trackId2, topN]);
  ```

---

### FE-35: EnhancementContext uses raw fetch() for 3 API endpoints, bypassing centralized API client
- **Severity**: MEDIUM
- **Dimension**: API Client & Data Fetching
- **Location**: `auralis-web/frontend/src/contexts/EnhancementContext.tsx:83,121,157`
- **Status**: NEW → #2653
- **Description**: The three mutation methods (`setEnabled`, `setPreset`, `setIntensity`) each use raw `fetch()` with hardcoded URL paths instead of the project's centralized `apiRequest` utility or `crudService`. While they DO check `response.ok` (unlike FE-26's `triggerLibraryScan`), they lack: (a) AbortController for cancellation on unmount, (b) centralized base URL configuration, (c) consistent error response parsing, and (d) retry logic for transient failures.
- **Evidence**:
  ```typescript
  // EnhancementContext.tsx:83-88 — raw fetch
  const response = await fetch(`/api/player/enhancement/toggle?enabled=${enabled}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  // EnhancementContext.tsx:121-126 — same pattern
  const response = await fetch(`/api/player/enhancement/preset?preset=${preset}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  // EnhancementContext.tsx:157-162 — same pattern
  const response = await fetch(`/api/player/enhancement/intensity?intensity=${clampedIntensity}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  ```
  Compare with `settingsService.ts` which uses `crudService` for all other settings operations.
- **Impact**: Enhancement API calls can't be cancelled on unmount (though the provider rarely unmounts), don't benefit from retry logic, and must be maintained separately from the API client pattern. If the API base URL changes (e.g., for production), these 3 endpoints will break.
- **Suggested Fix**: Create enhancement API functions in a service file using `apiRequest` or `crudService`, then call those from the context.

---

### FE-36: cacheSlice.clearCacheLocal spreads null `initialState.stats` and casts result as CacheStats
- **Severity**: LOW
- **Dimension**: Redux State / Type Safety
- **Location**: `auralis-web/frontend/src/store/slices/cacheSlice.ts:119-132`
- **Status**: NEW → #2654
- **Description**: The `clearCacheLocal` reducer spreads `initialState.stats` which is `null` (line 28). In JavaScript, `{...null}` is valid and produces an empty object — the spread is a no-op. The reducer then explicitly sets all known properties, so no fields are actually missing. However, the `as CacheStats` cast at line 132 bypasses TypeScript's structural checking, meaning if `CacheStats` gains new required fields in the future, this reducer won't produce a compile error.
- **Evidence**:
  ```typescript
  // cacheSlice.ts:27-28
  const initialState: CacheState = {
    stats: null,  // ← null!
    // ...
  };

  // cacheSlice.ts:119-132
  clearCacheLocal: {
    reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
      state.stats = {
        ...initialState.stats,  // ← {…null} → {} (no-op spread)
        tier1: { chunks: 0, size_mb: 0, hits: 0, misses: 0, hit_rate: 0 },
        tier2: { chunks: 0, size_mb: 0, hits: 0, misses: 0, hit_rate: 0 },
        overall: { ... },
        tracks: {},
      } as CacheStats;  // ← cast bypasses type checking
    },
  },
  ```
- **Impact**: Misleading code — the spread suggests `initialState.stats` contributes default values, but it's always null. The `as CacheStats` cast suppresses type errors if `CacheStats` is extended. No runtime bug today.
- **Suggested Fix**: Remove the `...initialState.stats` spread and the `as CacheStats` cast. Instead, construct a proper `CacheStats` literal that satisfies the type without casting.

---

### FE-37: Hardcoded CSS colors in 4 source files bypass design system tokens
- **Severity**: LOW
- **Dimension**: Design System
- **Location**: Multiple files (see evidence)
- **Status**: NEW → #2655
- **Description**: Four non-test source files use hardcoded hex color values instead of design system tokens. This is the same class of issue as FE-29 (SettingsDialogHeader) but in different files.
- **Evidence**:
  ```typescript
  // ErrorBoundary.tsx:79 — button text color
  color: '#fff',

  // lazyLoader.tsx:74 — error text color
  <div style={{ padding: '20px', textAlign: 'center', color: '#d32f2f' }}>

  // lazyLoader.tsx:100 — loading text color
  <div style={{ textAlign: 'center', color: '#666' }}>

  // lazyLoader.tsx:111-112 — error fallback
  color: '#d32f2f',
  border: '1px solid #d32f2f',

  // EditMetadataDialog.styles.ts:17-18 — dialog background
  bgcolor: '#1a1f3a',
  backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)',
  ```
  Note: `ErrorBoundary.tsx` already imports `tokens` and uses them for all other styles. `lazyLoader.tsx` renders fallback UI during lazy-load failures. `EditMetadataDialog.styles.ts` imports `tokens` but hardcodes dialog background.
- **Impact**: Colors don't adapt to theme changes. Inconsistent visual language. `lazyLoader.tsx` is somewhat defensible since the design system might not be loaded during lazy-load failures, but `ErrorBoundary.tsx` and `EditMetadataDialog.styles.ts` have no such excuse.
- **Suggested Fix**: Replace hardcoded values with `tokens.colors.*` equivalents. For `lazyLoader.tsx`, consider whether design system availability is guaranteed.

---

### FE-38: Vite loader script embeds 6 console calls that can't be tree-shaken
- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/vite.config.mts:64-86`
- **Status**: NEW → #2656 (addendum to FE-11)
- **Description**: The `fix-vendor-loading-order` Vite plugin injects a `<script>` tag with 6 `console.log`/`console.error` calls into the production HTML. Because these are inside a string template that gets injected at build time, they cannot be stripped by esbuild's `drop: ['console']` option (which only operates on parsed AST nodes in source files).
- **Evidence**:
  ```typescript
  // vite.config.mts:61-90 — string template with embedded console calls
  const loaderScript = `<script type="module">
    (async () => {
      try {
        console.log('[loader] Pre-loading vendor module...');       // line 64
        const vendor = await import('${vendorHref}');
        console.log('[loader] Vendor module imported...');          // line 68
        // ...
        console.log('[loader] Vendor initialization complete...');  // line 76
        const appModule = await import('${appSrc}');
        console.log('[loader] Application loaded successfully');    // line 80
      } catch (err) {
        console.error('[loader] Fatal loading error:', err);        // line 83
        console.error('[loader] Full error:', {msg, stack});        // line 86
      }
    })();
  </script>`;
  ```
- **Impact**: Every production page load prints 4 console.log messages. This supplements FE-11's finding — even if `esbuild.drop` is added to strip 412 source-level console calls, these 6 will persist. Minor performance and information leakage.
- **Suggested Fix**: Guard the non-error console calls with `if (import.meta.env.DEV)`, or replace them with comments. Keep `console.error` for the fatal error catch block since that's useful diagnostics.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| EnhancementContext callbacks with empty deps are stale | Callbacks use only stable values (`fetch` URL strings, `useState` setters). Empty deps are correct — the callbacks' behavior doesn't depend on any changing state. |
| `catch (error: any)` in similarityService.ts:148 is type-unsafe | Only 1 occurrence in production code. It accesses `error.statusCode` which is a custom property from the API client's error class. While `unknown` + type guard would be better, the `any` is pragmatic here. |
| WebSocket reconnect race condition with `singletonLastStreamCommand` | The singleton pattern is intentional and safe: only one WebSocket connection exists (singleton), and `singletonLastStreamCommand` is set synchronously in `send()`. The reconnect handler reads it after all queued messages are flushed. No actual race. |
| `themeConfig.ts` uses hardcoded `#667eea` and `#fff` | These ARE the theme definitions — they define what the tokens resolve to. Hardcoded colors in theme source files are intentional and correct. |
| EnhancementContext value not memoized | The EnhancementProvider uses `useCallback([], [])` for all 3 methods (stable refs) and only re-renders when its own state changes. When state changes, ALL consumers need the new values anyway. No unnecessary re-renders. |
| `processingService.uploadAndProcess` fragile JSON parsing | Line 233 `response.json()` on error responses could theoretically fail on non-JSON responses (e.g., 502 proxy HTML). However, the Auralis backend always returns JSON errors, and this function is only used in the Electron app context (no proxy). Defensive but not broken. |
| Missing error boundaries for Player, SimilarityVisualization | Root `<ErrorBoundary>` wraps `<App>` at top level. While per-subtree boundaries would improve granularity, the root boundary prevents full-app crashes. SimilarityVisualization handles its own error state. Not a bug. |
| `handleSettingChange` accepts `value: any` | Settings forms handle heterogeneous value types (string, number, boolean, string[]). The `any` is pragmatic. A discriminated union would be better but isn't a bug. |

## Dimension Checklist Summary

### Dimension 1: Component Quality
- [x] Single responsibility — hooks handle logic, components handle rendering
- [ ] **Size guideline** — FE-14 (Player.tsx 549 lines, QueuePanel 654 lines, open #2600)
- [x] Key stability — all lists use stable keys (FE-22 fixed in prior cycle)
- [x] Error boundaries — ErrorBoundary wraps `<App />` at root
- [ ] **Error display** — FE-27 (useSettingsDialog.error never rendered, open #2635)

### Dimension 2: Redux State Management
- [x] Normalized state — no duplication between slices
- [x] Selector memoization — comprehensive `createSelector` usage
- [ ] **Edge case** — FE-28 (setQueue([]) creates invalid -1 index, open #2636)
- [ ] **Misleading code** — FE-36 (clearCacheLocal spreads null, uses `as CacheStats`)
- [x] Async error handling — thunks dispatch error states
- [x] Serializable state — no functions or class instances in Redux

### Dimension 3: Hook Correctness
- [ ] **EnhancementContext isProcessing** — FE-25 (shared flag races, open #2633)
- [ ] **usePlayNormal handler subscriptions** — FE-18 (direct handler pass with `as any`, open #2604)
- [ ] **SimilarityVisualization async cleanup** — FE-34 (no abort/mount guard)
- [x] useEffect cleanup — WebSocket hooks, timers, AbortControllers properly cleaned up elsewhere
- [x] useLibraryData loadMore race — fixed in prior cycle

### Dimension 4: TypeScript Type Safety
- [x] **TypeScript version** — FE-24 **FIXED** (5.9.3, `tsc --noEmit` works)
- [ ] **Remaining `as any`** — 440 occurrences across 85 files (production + test combined)
- [ ] **WebSocketContext `any`** — FE-12 (open #2598)
- [ ] **Design system primitives `as any`** — FE-19 (open #2605)
- [ ] **`window as any`** — FE-23 (open #2620)
- [x] Domain types — correctly typed with `| null` for optional fields (TS 5.x fix)

### Dimension 5: Design System Adherence
- [x] Color.styles.ts migration — completed in prior cycle
- [ ] **Hardcoded `color: 'white'`** — FE-29 (SettingsDialogHeader, open #2637)
- [ ] **Hardcoded colors in 4 files** — FE-37 (ErrorBoundary, lazyLoader, EditMetadataDialog)
- [ ] **Relative imports** — FE-31 (settings components use `../../`, open #2639)
- [x] All other components use `@/design-system` tokens

### Dimension 6: API Client & Data Fetching
- [ ] **Raw fetch — settingsService** — FE-26 (triggerLibraryScan, open #2634)
- [ ] **Raw fetch — EnhancementContext** — FE-35 (3 API endpoints bypass apiRequest)
- [x] AbortController cleanup — per-request + unmount cleanup in API hooks
- [x] Transformer layer — per-entity snake→camel transformers intact
- [ ] **Type mismatch** — #2627 (ArtworkResponse `artwork_path` vs `artwork_url`)

### Dimension 7: Performance
- [ ] **Console logging in production** — FE-11 (412 occurrences, open #2597)
- [ ] **Vite loader console calls** — FE-38 (6 calls in string template, can't be tree-shaken)
- [ ] **Unused dependencies** — FE-32 (6 packages, open #2640)
- [ ] **ThemeContext cascading re-renders** — FE-33 (value not memoized)
- [x] List virtualization, position updates, bundle splitting — all intact

### Dimension 8: Accessibility
- [ ] **Scan progress** — FE-30 (ScanStatusCard missing aria-live, open #2638)
- [x] Queue toggle `aria-expanded` — fixed in prior cycle
- [x] ProgressBar ARIA, keyboard nav — intact
- [x] `@ts-ignore` — only 1 occurrence (test setup, justified)

### Dimension 9: Test Coverage
- [x] usePlayEnhanced — comprehensive test file (1,056 lines)
- [x] Player hooks, selectors, integration tests — all intact
- [x] No snapshot tests — proper assertion-based testing
- [x] 146 test files for frontend coverage
