# Frontend Audit — 2026-03-23

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality, Redux State, Hook Correctness, TypeScript, Design System, API Client, Performance, Accessibility, Test Coverage
**Method**: 5 parallel dimension agents (Sonnet), merged with dedup against 41 open frontend issues and 20 recent fix commits.
**Context**: Post-refactor audit — 20 commits since 2026-03-22 audit fixed ~25 previously reported issues.

## Executive Summary

This audit found **57 genuinely new findings** after aggressive deduplication against 41 open issues and 25+ recent fixes. No CRITICAL findings. The finding density is significantly lower than the 2026-03-22 audit (57 vs 98), confirming the refactor addressed the highest-impact issues.

**Key themes:**

1. **Test quality** (13 findings) — Tests that appear green but verify nothing: a 60-second real-time loop blocks CI, seek tests that never assert, source-text-only assertions that never render components, and a globally suppressed `act()` warning masking real bugs.

2. **Stale closures and unstable identities** (12 findings) — Despite many fixes, new instances emerged in `useEnhancedPlaybackShortcuts` (intensity stale closure), `useBatchOperations` (3 unstable arrows), `Player.tsx` (3 bare handlers recreated every 1s), and `useOptimizedCanvas` (renderFunction dep).

3. **Auto-fire on mount** (1 MEDIUM) — `CacheManagementPanel` calls `useStandardizedAPI('/api/cache/clear', {method: 'POST'})` without `autoFetch: false`, silently clearing cache every time settings are opened.

4. **Accessibility gaps in new components** (7 findings) — The refactor introduced new components (`RadialPresetSelector`, `EnergyField`, `CharacterTags`) that lack keyboard access and ARIA attributes.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 8 |
| LOW | 47 |
| **Total** | **57** |

---

## HIGH

---

### DIM1-01: onMuteToggle hard-codes 0.5 when unmuting — previous volume permanently lost
- **Severity**: HIGH
- **Dimension**: Component Quality
- **Location**: `auralis-web/frontend/src/components/player/Player.tsx:319`
- **Status**: NEW
- **Description**: `onMuteToggle` sets volume to `0.5` when unmuting instead of restoring the previous volume. The pre-mute volume is never stored. Every mute/unmute cycle resets user volume to 50%.
- **Evidence**: `handleVolumeChange(isMuted ? 0.5 : 0)`
- **Impact**: User loses their preferred volume level on every mute toggle.
- **Suggested Fix**: Store pre-mute volume in a ref. Restore on unmute.

---

### TC-NEW-1: useRestAPI.test.ts AbortError assertion contradicts implementation
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/hooks/api/__tests__/useRestAPI.test.ts`
- **Status**: NEW
- **Description**: Test asserts `error.toBeDefined()` for AbortError, but the implementation explicitly skips `setError` for AbortError (returns early). Test passes by coincidence and gives false confidence that abort error handling works.
- **Impact**: Any regression in AbortError handling would go undetected.
- **Suggested Fix**: Assert `error` is `null` after abort, matching the implementation's intentional skip.

---

## MEDIUM

---

### API-1: CacheManagementPanel auto-fires POST /api/cache/clear on every mount
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `auralis-web/frontend/src/components/shared/CacheManagementPanel.tsx`
- **Status**: NEW
- **Description**: `useStandardizedAPI('/api/cache/clear', { method: 'POST' })` called without `autoFetch: false`. Since `autoFetch` defaults to `true`, this fires `POST /api/cache/clear` on every component mount.
- **Impact**: Opening settings silently clears the entire audio cache.
- **Suggested Fix**: Add `autoFetch: false` to the options.

---

### DIM1-02: nextTrack/previousTrack reducers ignore repeatMode — optimistic index diverges
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `auralis-web/frontend/src/store/slices/queueSlice.ts`
- **Status**: NEW
- **Description**: `nextTrack` and `previousTrack` reducers don't check `repeatMode`. At end of queue with repeat-all, Redux sets `currentIndex = -1` while backend wraps to 0.
- **Impact**: UI shows "no track" briefly until WS broadcast corrects it. 200-500ms flicker.
- **Suggested Fix**: Check `repeatMode` in reducers — wrap index for repeat-all, keep index for repeat-one.

---

### PERF-4: AlbumCard creates per-card WS subscription — O(N) listeners for artwork_updated
- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `auralis-web/frontend/src/components/library/Items/albums/AlbumCard.tsx`
- **Status**: NEW
- **Description**: `useArtworkRevision(albumId)` creates a separate `useWebSocketSubscription(['artwork_updated'])` per card. With 50-album page, 50 listeners filter every WS message.
- **Impact**: Performance degradation with large album grids; O(N) message processing per WS event.
- **Suggested Fix**: Centralize to single listener with `Map<albumId, revision>`.

---

### A11Y-1: EnergyField CALM/AGGRESSIVE bar has no ARIA meter attributes
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/library/AlbumCharacterPane/EnergyField.tsx`
- **Status**: NEW
- **Description**: The energy bar renders as plain divs with no `role="meter"`, `aria-valuenow`, `aria-valuemin`, or `aria-valuemax`. WaveformVisualization's 7 frequency bars have no `aria-hidden`.
- **Suggested Fix**: Add `role="meter"` with aria-value attributes. Add `aria-hidden="true"` to decorative waveform.

---

### A11Y-4: RadialPresetSelector preset buttons are mouse-only Box divs
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `auralis-web/frontend/src/components/enhancement/RadialPresetSelector.tsx`
- **Status**: NEW
- **Description**: `PresetItem` buttons are `<Box>` divs with only `onClick` — no `role`, `tabIndex`, or `onKeyDown`. The enhancement preset selector is unreachable via keyboard.
- **Suggested Fix**: Add `role="radio"`, `tabIndex={0}`, `onKeyDown`, `aria-checked`.

---

### TC-NEW-2: progress-bar-monitoring.test.tsx has real 60-second wall-clock loop
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/progress-bar-monitoring/`
- **Status**: NEW
- **Description**: Test uses actual `setTimeout` (no fake timers) in a `while` loop that runs for 60 real wall-clock seconds, blocking a worker.
- **Suggested Fix**: Use `vi.useFakeTimers()` and `vi.advanceTimersByTime()`.

---

### TC-NEW-3: Seek test never asserts onSeek was called — test name is a lie
- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `auralis-web/frontend/src/tests/integration/player-controls/player-controls.test.tsx`
- **Status**: NEW
- **Description**: "should trigger seek when progress bar changed" only asserts `sliders.length > 0`. Never fires seek interaction, never asserts callback.
- **Suggested Fix**: Actually interact with the slider and assert `onSeek` was called with expected value.

---

## LOW

---

### Component Quality / Redux (5 LOW)

- **DIM1-03**: `connectionSlice.updateConnectionState` uses `Object.assign` without undefined filter — same pattern fixed in playerSlice (#3025) but not here.
- **DIM1-04**: `selectFormattedQueueTime` runs its own O(n) reduce instead of composing from `selectTotalQueueTime`.
- **DIM1-05**: `useQueueHistory.historyCount` state variable duplicates `history.length` — dead state.
- **DIM1-06**: `errorTrackingMiddleware.retryAction` returns on first iteration — catch block unreachable, retry logic is dead code.
- **DIM1-07**: `QueuePanel` four async handlers not `useCallback`-wrapped, inconsistent with drag handlers in same file.

### Hook Correctness / TypeScript (12 LOW)

- **DIM3-1**: `usePlayNormal` subscription split between call-time and unmount — concurrent calls accumulate duplicates.
- **DIM3-2**: `usePlayNormal` `(message.data as any).is_seek` — typed field exists on `AudioStreamStartMessage`.
- **DIM3-3**: `useQueueHistory.HistoryEntry.metadata` typed `Record<string, any>` — should be `unknown`.
- **DIM3-4**: `useQueueHistory` four async paths set state after await with no abort guard.
- **DIM3-5**: `useStandardizedAPI` `options.deps: any[]` spread into useEffect behind eslint-disable.
- **DIM3-6**: `useBatchOperations` three async handlers not `useCallback`-wrapped.
- **DIM3-7**: `usePlayerStreaming` position_changed callback typed `(msg: any)`.
- **DIM3-8**: `useLibraryWithStats.loadMore` mutates offset state before fetch — no rollback on failure.
- **DIM3-9**: `useSimilarTracks` API response mapped with `(item: any)`.
- **DIM3-10**: `useOptimizedCanvas` renderFunction in deps defeats memoization; data typed `any`.
- **DIM3-11**: `usePlaybackControl.play` isLoading window is zero — contradicts interface contract.
- **DIM3-12**: `useEnhancedPlaybackShortcuts` currentIntensity stale closure during rapid key presses.

### Design System (7 LOW)

- **DS-1**: `CacheHealthMonitor.refreshInterval` prop displayed but never forwarded to `useCacheHealth`.
- **DS-2**: `StreamingErrorBoundary` and `DebugInfo` use bare `'monospace'` instead of `tokens.typography.fontFamily.mono`.
- **DS-3**: Six components use hardcoded `rgba(239,68,68,0.1)` instead of `tokens.colors.utility.errorBg`.
- **DS-4**: `StreamingProgressBar` and `StreamingErrorBoundary` use 13 raw `borderRadius` values below design-system minimum.
- **DS-5**: `Player.tsx` error-banner uses `rgba(255,68,68,…)` — off-spec from canonical `#EF4444`.
- **DS-6**: `VolumeControl.tsx` onMouseLeave resets borderColor to hardcoded literal duplicating token.
- **DS-7**: `settingsService.updateSettings` casts to `Promise<any>` to suppress type mismatch.

### API Client (6 LOW)

- **API-2**: `useStandardizedAPI` auto-fetch effect has no cleanup/abort — setState after unmount.
- **API-3**: Four hooks (`useWebSocketStatus`, `useConnection`, `useCacheState`, `useCache`) select entire slices without `shallowEqual`.
- **API-4**: `useLibraryQuery.fetchMore` never sets `isLoading = true` for infinite-scroll pagination.
- **API-5**: `ConnectionStatusIndicator` "Reconnect" button uses `window.location.reload()` instead of `connect()`.
- **API-6**: ~31 unguarded `console.log`/`console.warn` calls in `usePlayEnhanced`/`usePlayNormal` fire in production.
- **API-7**: `settingsService.updateSettings` uses hardcoded ID `0` and casts to `Promise<any>`.

### Performance (6 LOW)

- **PERF-1**: `Player.tsx` three handlers not `useCallback`-wrapped, recreated every ~1s.
- **PERF-2**: `useLibraryWithStats` 8 unguarded `console.log` in hot paths.
- **PERF-3**: `Player.tsx` 11 unguarded `console.log`/`warn` calls.
- **PERF-5**: `useQueueStatistics`/`useQueueSearch` unconditional `console.warn` in render body.
- **PERF-6**: `ConnectionStatusIndicator` unconditional 5s health polling with no visibility guard.
- **A11Y-7**: `MediaCard` has no `:focus-visible` rule — MUI reset removes outline, no visible keyboard focus.

### Accessibility (5 LOW)

- **A11Y-2**: New `QueueTrackItem` uses `role="option"` but parent `<ul>` has no `role="listbox"`.
- **A11Y-3**: `ArtistListItem` button has no `aria-label`.
- **A11Y-5**: `CharacterTags` chips have no `aria-label`, no role, use `key={index}`.
- **A11Y-6**: `ConnectionStatusIndicator` aria-label updates but no `aria-live` for disconnect announcements.

### Test Coverage (6 LOW)

- **TC-NEW-4**: `E2E.test.tsx` misnamed — 14 tests only dispatch to store, never render components.
- **TC-NEW-5**: `Player.test.tsx` uses `fs.readFileSync` source-text assertions; component never rendered.
- **TC-NEW-6**: `setup.ts` globally suppresses `"not wrapped in act()"` warnings, masking real bugs.
- **TC-NEW-7**: `AlbumDetailView.test.tsx` entire 52-test suite is permanently `describe.skip`.
- **TC-NEW-8**: `ThemeToggle.test.tsx` 8 permanently `it.skip`'d tests.
- **TC-NEW-9-13**: `fingerprintToGradient.ts` (258 lines), `eraGrouping.ts`, `serviceFactory.ts`, `keyboardShortcutDefinitions.ts` (249 lines) have zero tests. `standardizedAPIClient.test.ts` and four hook tests use real sleeps adding 200+ ms latency.

---

## Relationships & Shared Root Causes

1. **Unstable callback identity** (PERF-1, DIM1-07, DIM3-6): `Player.tsx`, `QueuePanel`, and `useBatchOperations` all have bare arrow functions where `useCallback` is needed. A project-wide lint rule for `useCallback` on functions passed as props would prevent recurrence.

2. **Console pollution** (PERF-2, PERF-3, PERF-5, API-6): ~50+ unguarded console calls across hooks and components. A single ESLint `no-console` rule with `allow: ['error']` would catch these.

3. **Test quality illusion** (TC-NEW-1 through TC-NEW-5): Five tests appear green but verify nothing meaningful. These should be prioritized over new test creation.

4. **Missing abort guards** (DIM3-4, API-2): Multiple hooks perform async work without AbortController. Root cause: no project convention for async hook cleanup.

## Prioritized Fix Order

1. **API-1** — Auto-firing POST on mount clears cache silently. One-line fix, high user impact.
2. **DIM1-01** — Volume loss on mute/unmute. Quick ref fix, affects every user.
3. **TC-NEW-2** — 60-second wall-clock test blocks CI. Switch to fake timers.
4. **TC-NEW-1** — Fix the inverted assertion before it masks a real regression.
5. **A11Y-4** — RadialPresetSelector keyboard access. New component needs ARIA from the start.
6. **PERF-4** — Per-card WS subscription. Scale issue for large libraries.
7. **DIM1-02** — RepeatMode in reducers. Prevents end-of-queue flicker.
8. **Console cleanup** — Bulk fix ~50 sites with ESLint rule.

---

*Report generated by Claude Opus 4.6 — 2026-03-23*
*Suggest next: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-03-23.md`*
