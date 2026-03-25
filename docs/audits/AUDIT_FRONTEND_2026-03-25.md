# Frontend Audit — 2026-03-25

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: React 18 frontend — `auralis-web/frontend/src/`
**Dimensions**: Component Quality, Redux State, Hook Correctness, TypeScript, Design System, API Client, Performance, Accessibility, Test Coverage
**Method**: 5 parallel agents (Sonnet), merged with deduplication against 30 open frontend issues + 37 concurrency issues

## Executive Summary

Post-refactor audit following ~30 fix commits. **53 new findings**: 4 HIGH, 14 MEDIUM, 35 LOW. Significant improvement from prior audits — many previous HIGH/MEDIUM findings now resolved.

**Key clusters:**

1. **setResumePositionGetter singleton race** (DIM-1-01) — Both play hooks write to the same WS context slot; wrong engine's position used on reconnect.

2. **Hook stability** (HC-1, HC-2, DIM-5-API-01) — usePlayNormal still rebuilds WS subscriptions per-call; useLibraryWithStats reads stale offset; useRestAPI return object changes identity every render.

3. **Accessibility gaps** (10 findings) — ArtistHeader, SearchBar, SimilarTracksModal missing aria-labels. Table headers lack scope. Batch toolbar lacks role.

4. **Test fidelity** (8 findings) — DraggableTrackRow mock targets wrong path. ArtistDetailView tests only assert container exists. BatchActionsToolbar swallows assertion failures.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 14 |
| LOW | 35 |
| **Total** | **53** |

## Prior Findings Status

~30 issues fixed since 2026-03-23 audit, including:
- Player useCallback wrapping (#3246, #3243)
- shallowEqual on whole-slice selectors (#3123)
- CacheManagementPanel autoFetch (#3247)
- connectionSlice undefined filter (#3233)
- cacheSlice naming (#3120)
- AbortController in useStandardizedAPI (#3234)
- Various type safety, a11y, and test fixes

---

## New Findings

### HIGH

---

### DIM-1-01: setResumePositionGetter last-writer-wins race between play hooks
- **Severity**: HIGH
- **Dimension**: Component Quality / Hook Correctness
- **Location**: `hooks/enhancement/usePlayEnhanced.ts`, `hooks/enhancement/usePlayNormal.ts`, `contexts/WebSocketContext.tsx`
- **Status**: NEW
- **Description**: Both usePlayEnhanced and usePlayNormal write to the same singleton slot in WebSocketContext. Last-mounted hook wins. On WS reconnect, wrong engine's position sent as start_position. Cleanup path also racy — unmounting hook can null out legitimate getter.
- **Impact**: Wrong seek position on reconnect; silent audio offset.
- **Suggested Fix**: Use separate getter slots per engine, or derive from Redux player state.

---

### A11Y-01: ArtistHeader "More Options" IconButton missing aria-label
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `components/library/Items/artists/ArtistHeader.tsx`
- **Status**: NEW
- **Impact**: WCAG 4.1.2 failure — screen readers cannot identify button purpose.

---

### A11Y-02: SearchBar SearchTextField has no accessible label
- **Severity**: HIGH
- **Dimension**: Accessibility
- **Location**: `components/shared/SearchBar.tsx`
- **Status**: NEW
- **Impact**: Placeholder-only label disappears on input, inaccessible.

---

### TC-01: DraggableTrackRow.test.tsx mock targets wrong resolved path — 20 tests built on broken mock
- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `components/library/__tests__/DraggableTrackRow.test.tsx`
- **Status**: NEW
- **Impact**: All 20 tests pass vacuously. Regressions in drag-reorder undetected.

---

### MEDIUM

---

### HC-1: usePlayNormal rebuilds WS subscriptions per playNormal() call
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `hooks/enhancement/usePlayNormal.ts`
- **Status**: NEW
- **Description**: Subscriptions torn down and rebuilt inside callback, creating message-loss window. Correct pattern (mount-only) used by usePlayEnhanced.

---

### HC-2: useLibraryWithStats.fetchTracks reads stale offset from closure
- **Severity**: MEDIUM
- **Dimension**: Hook Correctness
- **Location**: `hooks/library/useLibraryWithStats.ts`
- **Status**: NEW
- **Description**: offset excluded from useCallback deps with eslint-disable. useLibraryData fixed this with offsetRef; this hook didn't adopt the fix.

---

### DIM-5-API-01: useRestAPI return object changes identity every render
- **Severity**: MEDIUM
- **Dimension**: API Client
- **Location**: `hooks/api/useRestAPI.ts`
- **Status**: NEW
- **Description**: Spreads stableMethods into new object on every return, causing downstream executeQuery/fetchMore to be recreated.

---

### DIM-1-02: ConnectionStatusIndicator duplicates Redux connectionSlice state
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `components/shared/ConnectionStatusIndicator.tsx`
- **Status**: NEW

---

### DIM-1-03: PlayerEnhancementPanel unconditional console.log in production (useMemo side effect)
- **Severity**: MEDIUM
- **Dimension**: Component Quality
- **Location**: `components/enhancement/PlayerEnhancementPanel.tsx`
- **Status**: NEW

---

### DIM-1-04: Duplicate selectCurrentQueueTrack — memoized vs unmemoized
- **Severity**: MEDIUM
- **Dimension**: Redux State
- **Location**: `store/selectors/index.ts`, `store/slices/queueSlice.ts`
- **Status**: NEW

---

### TS-1: useWebSocketErrors double-cast `as unknown as WebSocketErrorMessage`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `hooks/websocket/useWebSocketErrors.ts`
- **Status**: NEW

---

### TS-2: useOptimisticUpdate `Args extends any[]` should be `unknown[]`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `hooks/shared/useOptimisticUpdate.ts`
- **Status**: NEW

---

### TS-3: useStandardizedAPI body/deps typed `any`, usePaginatedAPI defaults `T = any`
- **Severity**: MEDIUM
- **Dimension**: Type Safety
- **Location**: `hooks/shared/useStandardizedAPI.ts`
- **Status**: NEW

---

### A11Y-03: QueuePanel error banner missing role=alert
- **Severity**: MEDIUM
- **Dimension**: Accessibility
- **Location**: `components/player/QueuePanel.tsx:196-200`

### A11Y-04: TrackTableHeader/TracksTableHeader cells missing scope=col
- **Severity**: MEDIUM
- **Dimension**: Accessibility

### A11Y-05: SelectableTrackRow checkbox missing track-context aria-label
- **Severity**: MEDIUM
- **Dimension**: Accessibility

### A11Y-06: BatchActionsToolbar lacks role=toolbar and aria-label
- **Severity**: MEDIUM
- **Dimension**: Accessibility

### TC-02: ArtistDetailView.test.tsx — 22 tests only assert container exists
- **Severity**: MEDIUM
- **Dimension**: Test Coverage

### TC-03: BatchActionsToolbar.test.tsx — try/catch swallows assertion failures
- **Severity**: MEDIUM
- **Dimension**: Test Coverage

### TC-04-TC-06: SimilarTracksModal, AlbumCharacterPane family, EnhancementToggle — zero tests
- **Severity**: MEDIUM
- **Dimension**: Test Coverage

---

### LOW (35 findings)

**Component Quality**: DIM-1-05 (StarfieldBackground 558 lines), DIM-1-06 (error history index keys), DIM-1-07 (updatePlaybackState undefined filter), DIM-1-08 (ConnectionStatusIndicator empty timer), DIM-1-09 (Player volume triple-derivation)

**Hook Correctness**: HC-3 (useStandardizedAPI AbortController never connected to fetch), HC-4 (usePlayerStreaming driftThreshold not memoized), HC-5 (setEnabled delegates to toggleEnabled), HC-6 (useQueueHistory duplicated setIsLoading), HC-7 (useAudioVisualization busy rAF loop)

**Type Safety**: TS-4 (position_changed typed any), TS-5 (useLibraryWithStats response.json any), TS-6 (useQueueHistory catch as ApiError without narrowing), TS-7 (useFingerprintCache null cast), TS-8 (useOptimizedCanvas data typed any)

**Design System**: DIM-5-DS-01 (CacheHealthMonitor/AdvancedSettingsPanel hardcoded rgba), DIM-5-DS-02 (AppEnhancementPaneHeader hardcoded icon color), DIM-5-DS-03 (skeleton loaders sub-token borderRadius), DIM-5-DS-04 (exportInfrastructure hardcoded canvas colors)

**API Client**: DIM-5-API-02 (useBatchOperations unstable returns), DIM-5-API-03 (useCacheHealth unreachable 'warning' status), DIM-5-API-04 (useLibraryWithStats fetch without AbortController)

**Performance**: DIM-5-PERF-01 (TrackListViewContent inline arrow defeating memo), DIM-5-PERF-02 (useCacheHealth/Stats query.refetch in deps), DIM-5-PERF-03 (useLibraryWithStats inline arrow to WS subscription)

**Accessibility**: A11Y-07 (CharacterTags role=status should be list), A11Y-08 (LibraryHeader emoji not aria-hidden), A11Y-09 (CozyAlbumGrid no role/label), A11Y-10 (SimilarTracksModal close missing aria-label)

**Test Coverage**: TC-07 (ClearQueueDialog zero tests), TC-08 (ArtistInfoModal zero tests)

---

## Relationships

1. **Play hook architecture**: DIM-1-01 (singleton race) + HC-1 (subscribe-in-callback) share root cause — usePlayNormal diverges architecturally from usePlayEnhanced. Refactoring usePlayNormal to match usePlayEnhanced's mount-time subscription pattern fixes both.

2. **Return stability chain**: DIM-5-API-01 (useRestAPI identity) → HC-2 (stale offset) — unstable return identity propagates through all consumers. Memoizing the return object fixes cascading re-renders.

3. **Test fidelity cluster**: TC-01 (wrong mock path) + TC-02 (assert-container-only) + TC-03 (swallowed assertions) — three different patterns that make tests pass vacuously. A single test health sweep would catch all three.

## Prioritized Fix Order

1. **DIM-1-01** — setResumePositionGetter race. Wrong seek on reconnect.
2. **TC-01** — DraggableTrackRow mock path. 20 broken tests.
3. **DIM-5-API-01** — useRestAPI return identity. Root cause of cascading re-renders.
4. **HC-1** — usePlayNormal subscribe pattern. Align with usePlayEnhanced.
5. **A11Y-01 + A11Y-02** — Missing aria-labels on primary UI controls. WCAG compliance.
6. **DIM-1-04** — Duplicate selector names. Developer confusion risk.
7. **HC-2** — Stale offset closure. Use offsetRef pattern from useLibraryData.

---

*Report generated by Claude Opus 4.6 — 2026-03-25*
*Suggest next: `/audit-publish docs/audits/AUDIT_FRONTEND_2026-03-25.md`*
