---
description: "Deep audit of the React frontend — components, Redux, hooks, TypeScript, design system, accessibility"
argument-hint: "[--focus <dimensions>] [--depth shallow|deep] [--limit <N>]"
---

# Frontend Audit

Perform a deep audit of the Auralis React frontend — components, Redux, hooks, TypeScript, design system, accessibility.

**Architecture**: This is an orchestrator. Each dimension runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--focus <dimensions>`: Comma-separated dimension numbers or names (e.g., `1,3` or `components,hooks,redux`). Default: all 9.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full call graphs. Default: `deep`.
- `--limit <N>`: Stop after N findings (useful for time-boxed audits). Default: unlimited.

## Scope

This audit covers ONLY the frontend code:

- **Components**: `auralis-web/frontend/src/components/`
- **Hooks**: `auralis-web/frontend/src/hooks/` (api, app, audio, enhancement, fingerprint, library, player, shared, websocket)
- **Contexts**: `auralis-web/frontend/src/contexts/` — `ThemeContext.tsx`, `WebSocketContext.tsx`, `PlaybackSessionContext.tsx` (+ `playbackSessionContexts.ts` — the single shared enhanced-audio streaming session — and `usePlaybackSessionHooks.ts`, the transport command gate, start-retry and auto-advance hooks the provider composes, #5840). `websocketTypeDiagnostics.ts` holds the provider's unregistered-message-type diagnostics (#5841). There is **no** EnhancementContext; do not report against one.
- **Store**: `auralis-web/frontend/src/store/` (`slices/`, `selectors/`, `middleware/`)
- **Services**: `auralis-web/frontend/src/services/` (API clients + `api/`, `audio/` subdirs; the *fingerprint/* subdir was deleted with `FingerprintCache` in #5215); payload mapping in `auralis-web/frontend/src/api/transformers/`
- **Types**: `auralis-web/frontend/src/types/` (`api.ts`, `domain.ts`, `websocket.ts`, `ws/`)
- **Design System**: `auralis-web/frontend/src/design-system/` (tokens, theme) and `auralis-web/frontend/src/theme/` (`themeConfig.ts` composes `themePalette.ts` / `themeTypography.ts` / `themeComponents.ts`, #5841); global CSS-in-JS in `auralis-web/frontend/src/styles/globalStyles.ts` (+ `globalKeyframes.ts`, `globalUtilities.ts`). There is no *index.css* (deleted, #5642).
- **Tests**: `auralis-web/frontend/src/test/` (utils + global setup), plus specs in `auralis-web/frontend/src/__tests__/`, `auralis-web/frontend/src/tests/`, and co-located `*.test.tsx`
- **Other**: `auralis-web/frontend/src/a11y/` (`focusManagement.ts`), `auralis-web/frontend/src/utils/`, `auralis-web/frontend/src/api/` (`responseGuards.ts`, `transformers/`), `auralis-web/frontend/src/config/api.ts`, `auralis-web/frontend/src/config/timing.ts` (shared `QUERY_STALE_TIME_MS` / `QUERY_GC_TIME_MS` / `SEARCH_DEBOUNCE_MS`, #5800, #6221, and the WebSocket reconnect budget `DEFAULT_MAX_RECONNECT_ATTEMPTS` / `DEV_MAX_RECONNECT_ATTEMPTS`, #6220)
- **Config**: `auralis-web/frontend/vite.config.mts`, `auralis-web/frontend/vitest.config.ts`, `auralis-web/frontend/tsconfig.json`, `auralis-web/frontend/package.json` (pnpm is the only supported package manager)

Out of scope: Python backend, audio engine, Rust DSP, database.

## Severity Examples

| Severity | Frontend-Specific Examples |
|----------|--------------------------|
| **CRITICAL** | Dropped audio frames from WebSocket, unescaped metadata rendering (XSS), Redux state corruption causing crash |
| **HIGH** | Stale closure causing wrong track to play, WebSocket reconnect losing state, memory leak in audio hooks |
| **MEDIUM** | Missing error boundary, inconsistent loading states, hardcoded colors bypassing design tokens |
| **LOW** | Component exceeding 300 lines, missing type annotations, dead imports, undocumented props |

## Audit Dimensions

### Dimension 1: Component Quality

**Check**:
- [ ] Single responsibility — does each component do ONE thing? Are any > 300 lines? After the #5478 / #5840 / #5841 split waves, `auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts` was brought back under 300 (295, #6037, 4e0ca01db) and the #6275 hook splits (`useAudioStreamingCore.ts` 250, `useStreamMessageHandlers.ts` 194, with the extracted `streamingCoreLifecycle.ts`, `audioChunkIngest.ts`, `useLibraryQueryFetchers.ts`, `useQueueEditMutations.ts` / `useQueueModeMutations.ts` over `queueMutationRunner.ts`) cleared the other two; at HEAD the only non-test `src/` file over 300 is `auralis-web/frontend/src/components/library/CozyLibraryView.tsx` (335). Re-measure with `wc -l` rather than trusting this. A hook whose file is under 300 only because it is one 200+ line function is the #6275 pattern: look at function length, not just file length.
- [ ] Prop drilling — are props passed through > 2 intermediate components instead of using context or Redux?
- [ ] Conditional rendering — any branches that produce inconsistent DOM structure causing React reconciliation issues?
- [ ] Key usage in lists — stable keys derived from data, never array indices for reorderable lists?
- [ ] Ref usage — are refs used correctly for imperative operations (audio elements, scroll, focus)?
- [ ] Error boundaries — are they wrapping critical subtrees (player, library, enhancement)? There is one implementation, `auralis-web/frontend/src/components/core/ErrorBoundary.tsx` (fallback `(error, retry) => node`, `resetKeys`), with `RegionErrorFallback.tsx` as the shared fallback (#5627); the design-system duplicate is gone. A static "refresh the page" fallback that makes retry unreachable, or a second boundary class, is a finding. Region boundaries must also recover (#6035, fixed in 090e19edc and 7b83ba475): the Settings and shortcuts-help fallbacks close their dialog before retrying (else a still-open dialog re-throws), the Player and queue-panel boundaries take the current track id as `resetKeys` so a bad track does not re-crash every retry, and the three `React.lazy` route imports in `auralis-web/frontend/src/ComfortableApp.tsx` go through `auralis-web/frontend/src/utils/lazyWithRetry.tsx` (retry with back-off, then a fresh import after the boundary's reset, via `ErrorBoundaryResetContext`), pinned by `auralis-web/frontend/src/utils/__tests__/lazyWithRetry.test.tsx`. Regression guard: a bare `React.lazy` route import caches a rejected chunk load, so a boundary retry re-throws it. `ErrorBoundary`'s `onError` prop is still passed by no region; that is not a filed defect.
- [ ] Unmounted component updates — do async operations check component mount state before setState?

### Dimension 2: Redux State Management

**Check**:
- [ ] Slice design — is state normalized? Are there duplicated pieces of state that can go out of sync?
- [ ] Selector memoization — are selectors using `createSelector` where derived data is computed? Any selectors returning new references on every call?
- [ ] Dispatch ordering — can rapid dispatches (skip, skip, skip) leave the store in an inconsistent intermediate state?
- [ ] Thunk / async action error handling — are rejected promises caught and dispatched as error states?
- [ ] Middleware — any custom middleware that could drop or reorder actions? `auralis-web/frontend/src/store/index.ts` chains `errorTrackingMiddleware` always and `loggerMiddleware` only under `import.meta.env.DEV` (#3622); loggerMiddleware has no scattered `any` (#5377). The four slices (`player`, `queue`, `cache`, `connection`) are the exported `reducer` map that `auralis-web/frontend/src/test/test-utils.tsx` builds its test store from, with the default middleware (serializable and immutable checks on) as in production (#5681, fixed in 880fb589b and bb72d3e1e), so a slice added to the store cannot be missing from tests; a test store that hand-lists slices, or a spec that turns `serializableCheck` off (none does at HEAD), is a finding. The `connection` slice is write-dead in production (nothing sets `wsConnected`): that is #5615, open, so report it only as Existing: #5615.
- [ ] Selectors — `auralis-web/frontend/src/store/selectors/` holds only `player.ts` and `queue.ts` (+ the `index.ts` barrel); the dead cache/connection/combined selector cluster was deleted and `playerSelectors` now groups the slice's own selectors instead of redefining them (#5129, #6040, 13603c945). A second selector definition for the same field, or a selector with no production consumer, is a finding.
- [ ] State shape — are there deeply nested objects that make immutable updates error-prone?
- [ ] Serializable state — are non-serializable values (functions, class instances, Promises) stored in Redux?

### Dimension 3: Hook Correctness

**Check**:
- [ ] Dependency arrays — missing deps causing stale closures? Excess deps causing infinite re-renders?
- [ ] `useEffect` cleanup — do WebSocket hooks close connections? Do timers get cleared? Do subscriptions unsubscribe?
- [ ] `useCallback` / `useMemo` — are expensive computations memoized? Are callback identities stable for child components?
- [ ] Custom hook return stability — do hooks return the same reference shape on every render?
- [ ] Race conditions — can an effect fire with outdated closure values after rapid state changes?
- [ ] WebSocket hooks (`auralis-web/frontend/src/hooks/websocket/`: `useWebSocketConnection.ts`, `websocketConnectionCore.ts`, `websocketConnectionState.ts`, `useWebSocketMessages.ts`, `useWebSocketErrors.ts`, `useOutgoingChannel.ts`, `socketFrameParser.ts`) — reconnection logic, message queue during disconnect, binary frame parsing. Cross-check against `auralis-web/frontend/src/contexts/WebSocketContext.tsx`. `useReconnectOnNetwork.ts` re-arms a connection that gave up when the browser goes `online` or the window becomes visible (#5917), and `websocketConnectionLifecycle.ts` holds the singleton manager construction and handler wiring split out of `useWebSocketConnection` (#6275). Client-to-server commands are a discriminated union, `OutgoingCommand` in `auralis-web/frontend/src/types/ws/commands.ts` (#6050, 2ae839049); a hand-built `{ type: string; data?: Record<string, unknown> }` send, or a camelCase field (`trackId`) on a command, is a finding. The reconnect policy has one definition, `DEFAULT_WEBSOCKET_CONFIG` in `auralis-web/frontend/src/utils/errorHandling.ts` (#5800), and its attempt budget has one source, `DEFAULT_MAX_RECONNECT_ATTEMPTS` in `auralis-web/frontend/src/config/timing.ts`: the manager default, the hook's production cap and the Redux connection slice's initial `maxReconnectAttempts` (which feeds `canReconnect`) all derive from it (#6220). A re-typed attempt count, or a slice value that disagrees with the manager, is a finding.
- [ ] Subscription lifecycle — `useMessageSubscriptions(subscribe, handlers)` in `useWebSocketMessages.ts` is the one ref-held, type-keyed subscribe effect (#5789; the #4668 / #5621 no-resubscribe guarantee lives there). `usePlayerStateSync` and `usePlaylistWebSocket` were moved onto it (#6041, 23e4e07c3); `useArtworkUpdates` and `useScanProgress` still hand-roll a subscribe effect. A hook that hand-rolls its own subscribe/unsubscribe effect instead is a finding.
- [ ] Player hooks (`hooks/player/`) — do they correctly synchronize with backend playback state? Stale position/duration?
- [ ] API hooks (`hooks/api/`) — cancellation of in-flight requests on unmount? Deduplication of concurrent identical requests?
- [ ] Single-flight playback start — `startPlayback` in `AudioPlaybackEngine` is single-flight, and a stop/dispose during its awaited AudioContext resume / worklet load cancels it (#6043, aa05a0f7c); a path that issues another start per landing chunk, or that can create a worklet node on a stopped/disposed engine, is a finding.
- [ ] Streaming session ownership — `auralis-web/frontend/src/contexts/PlaybackSessionContext.tsx` holds the single shared enhanced-audio session. Does any hook or component open its own session or `AudioContext` alongside it?

### Dimension 4: TypeScript Type Safety

**Check**:
- [ ] `any` usage — are there `any` types that bypass safety? Should they be `unknown` or properly typed?
- [ ] Type assertions (`as`) — are there unsafe casts that could mask runtime errors?
- [ ] API response types — do they match the actual backend response schemas in `auralis-web/backend/schemas/`?
- [ ] WebSocket message types — are binary and text message types correctly discriminated? Subscribe handlers are typed per message type, so consumers are compile-checked against `types/ws/*` (#5636); a hand-written cast of a handler payload is a finding.
- [ ] Shared unions — `RepeatMode` and `StreamType` each have one definition in `auralis-web/frontend/src/types/domain.ts` (#6048, d1fca07d0); other modules import or re-export them (a type-level test pins the re-exports). A re-typed `'off' | 'all' | 'one'` or inline `stream_type` literal union is a finding.
- [ ] Event handler types — are DOM event types correctly specified?
- [ ] Union exhaustiveness — are switch/if chains over union types exhaustive (use `never` checks)?
- [ ] Generic constraints — are generic hooks and utilities properly constrained?
- [ ] Preset union — `EnhancementPreset` in `auralis-web/frontend/src/types/domain.ts` is `'adaptive'` only (2026-09-13), with `ENHANCEMENT_PRESETS` / `isEnhancementPreset` beside it. Since #5610 every other site derives from it rather than redeclaring a union (`types/ws/enhancement.ts`, `PresetName` in `store/slices/playerSlice.ts`, `services/settingsService.ts`, `hooks/enhancement/`), and wire strings narrow through `isEnhancementPreset` (`hooks/player/playerStateSnapshot.ts`), not an `as` cast; `types/ws/streaming.ts` widens it to `EnhancementPreset | 'none'` on purpose. A redeclared preset union, a preset typed as bare `string`, an `as EnhancementPreset` cast, or UI still offering a removed preset is a finding; a single-option preset control is intended.

### Dimension 5: Design System Adherence

**Check**:
- [ ] Token usage — are ALL colors sourced from `import { tokens } from '@/design-system'`? Any hardcoded hex/rgb values? The unread token groups (`visualization`, `numbersPolicy`, `audioReactive`, `elevation`, `opacity`, `blur`, `lightMode.neon`, several gradients and `utility.*` entries) and the unreferenced global utility classes/keyframes in `auralis-web/frontend/src/styles/` were deleted (#6062, fc02e2a8f, a2d31dc77); a reference to one is a stale name that should fail `type-check`, and re-adding a token with no consumer is a finding.
- [ ] Spacing — consistent use of spacing tokens vs arbitrary pixel values?
- [ ] Typography — font sizes, weights, line heights from tokens?
- [ ] Responsive — do components use responsive breakpoints from the design system?
- [ ] Dark/light theme — do all styled elements respect the theme context? Literals that equal a design token must use it, and `auralis-web/frontend/src/design-system/__tests__/spacingTokens.test.ts` source-scans for them (#5648); MUI breakpoints derive from `tokens.breakpoints` (#6059); fonts are bundled, not loaded from Google Fonts (#6060, pinned by `auralis-web/frontend/src/__tests__/bundledFonts.guard.test.ts`).
- [ ] Import paths — all using `@/` absolute imports, no relative `../../` paths? `auralis-web/frontend/src/__tests__/relativeImports.guard.test.ts` fails on any deep-relative import or `vi.mock` path (#6061).

### Dimension 6: API Client & Data Fetching

**Check**:
- [ ] Error handling — are HTTP errors (4xx, 5xx) caught and surfaced to the UI?
- [ ] Loading states — is there a loading indicator for every async operation?
- [ ] Request cancellation — are fetch/axios requests cancelled on component unmount? Superseded/unmounted React Query queries cancel their HTTP request (#5650). `apiRequest` rethrows a caller-initiated abort unchanged as the raw `AbortError` (test with `isAbortError` from `auralis-web/frontend/src/utils/errorGuards.ts`); only its own timeout surfaces as `APIRequestError` status 0 (#5653). A catch that toasts "Network error" on an abort, or re-checks the signal because it distrusts this, is a finding.
- [ ] Retry logic — are transient failures (network, 503) retried? Are non-transient failures (400, 404) NOT retried? The React Query policy is `shouldRetryQuery` in `auralis-web/frontend/src/utils/queryRetry.ts` (keyed on `APIRequestError`'s status, #4467); flag a call site with its own retry rule.
- [ ] Response validation — runtime guards live in `auralis-web/frontend/src/api/responseGuards.ts`. Do the fetch paths actually route through them, or do some cast the JSON straight to a type and trust it? The transport takes a guard per call (#6063, 6b3207650 and earlier parts): similar tracks, search, library stats, fingerprints, album tracks, artist detail, create-playlist, `addTracksToPlaylist` and `addTracksToQueue` check the field their consumer reads; a new call site that only asserts the type is a finding. The wire types in `auralis-web/frontend/src/api/transformers/types.ts` carry every field the backend model serializes, pinned in both directions by `tests/backend/test_api_types_cover_responses_5131.py` (#5131, e83bb7c13). A guard that exists but is unused is worse than none — it implies coverage that isn't there.
- [ ] Error normalization — are HTTP failures funnelled through `auralis-web/frontend/src/utils/httpError.ts` / `errorGuards.ts`, or does each call site re-implement error shape handling? User-facing failure text goes through `failureMessage(prefix, err)` in `errorGuards.ts` (#5652, 5f63d9431), which yields `"<prefix>: <backend detail>"`; a toast or settings error that interpolates the error object (`${err}` doubles the `APIRequestError:` name) or shows a fixed literal that drops the backend's reason is a finding.
- [ ] Base URL configuration — is the API base URL sourced from `auralis-web/frontend/src/config/api.ts`, not hardcoded per call site? `API_BASE_URL` / `WS_BASE_URL` there: a production page uses its own origin (#5886), `VITE_API_URL` alone also moves the WebSocket and `VITE_WS_URL` still wins (#5654). A library-scan request must pass `SCAN_TIMEOUT_MS`, not the 30s default (#5643).
- [ ] One transport — REST hooks should go through `useRestAPI.ts` (a React wrapper over the shared `fetchWithTimeout` / `buildUrl` in `utils/apiRequest.ts`; it has no transport of its own since *restApiTransport.ts* was deleted, #6216) or `auralis-web/frontend/src/utils/apiRequest.ts` (including its `getOrNullOn404` helper for fingerprint-style 404-means-absent reads, #6221), with the timeout from `DEFAULT_TIMEOUT_MS` in `auralis-web/frontend/src/utils/apiRequestTypes.ts` and stale time / debounce from `auralis-web/frontend/src/config/timing.ts` (#5800, a test pins numeric `staleTime` literals out). A bare `fetch` with no timeout, or a re-typed timeout/stale/debounce literal, is a finding.
- [ ] camelCase/snake_case — is the casing conversion between frontend (camelCase) and backend (snake_case) handled consistently?

### Dimension 7: Performance

**Check**:
- [ ] Unnecessary re-renders — are components re-rendering when their props haven't changed? Missing `React.memo`?
- [ ] Large list rendering — are lists with 100+ items virtualized?
- [ ] Bundle size — are there large dependencies that could be lazy-loaded or tree-shaken?
- [ ] Image optimization — are artwork images lazy-loaded? Proper sizing?
- [ ] WebSocket message rate — can high-frequency messages (position updates) flood React renders?
- [ ] Audio buffer memory — are Web Audio API buffers released when tracks change?
- [ ] Effect cascades — does one state change trigger a chain of effects that could be batched?

### Dimension 8: Accessibility

**Check**:
- [ ] Keyboard navigation — can all interactive elements be reached and activated via keyboard?
- [ ] ARIA labels — do custom controls (sliders, progress bars, play/pause) have proper ARIA attributes?
- [ ] Focus management — is focus correctly managed after modal open/close, route changes, and dynamic content? Helpers live in `auralis-web/frontend/src/a11y/focusManagement.ts`; flag components that hand-roll focus traps instead of using them.
- [ ] View announcements — does `auralis-web/frontend/src/components/core/AppViewAnnouncement.tsx` announce view changes to screen readers, and is there exactly one `<h1>` per view (a specced invariant — see the co-located tests)?
- [ ] Screen reader — are player state changes (now playing, paused) announced? Info/success alerts and toasts are polite status regions, not assertive alerts (#5669).
- [ ] Reduced motion — animated surfaces (the starfield background, auto-rotating text) honour `prefers-reduced-motion` through the one shared hook `auralis-web/frontend/src/hooks/shared/usePrefersReducedMotion.ts` (#5676, #6036); a second matchMedia check is a finding.
- [ ] Color contrast — do text and interactive elements meet WCAG AA contrast ratios?
- [ ] Semantic HTML — are headings hierarchical? Are lists using `<ul>`/`<ol>`? Are buttons vs links correct?

### Dimension 9: Test Coverage

**Check**:
- [ ] Critical path coverage — are player hooks, WebSocket hooks, and Redux slices tested?
- [ ] Global auto-mocks — `auralis-web/frontend/src/test/setup.ts` mocks `contexts/WebSocketContext` for every spec. Any test claiming to exercise the real implementation must `vi.unmock()` it; flag ones that don't (they are asserting against the mock).
- [ ] Pre-existing failures — the known-failing specs are listed explicitly in `auralis-web/frontend/test-baseline.json` (#4640). **Read that file before reporting any failing spec**; if it is listed, do not file it. The baseline is empty at HEAD (all 49 entries repaired, #6076, 52929bb09), so any failing spec is a real regression. Verify with `pnpm run test:ci && pnpm run test:baseline -- --strict-stale` (what CI runs, with `VITEST_EXIT_CODE` handed to the gate). The gate is a ratchet (baseline may shrink, never grow), so a failure *not* in the list is a real regression; under `--strict-stale` it also fails on a listed test that ran and passed (#5344) and on a phantom entry naming a test that no longer exists (#5811). Since #5679 (86f5299a9) it also fails when the run collected under 90% of `generatedFrom.totalTests` recorded in the baseline (deliberate spec deletions are acknowledged by `test:baseline:update`) and when vitest exited non-zero with no failing test in the report. Regenerate with `pnpm run test:baseline:update` (it first runs `auralis-web/frontend/scripts/check-installed-deps.mjs`, which refuses while the installed jsdom/vitest differ from `pnpm-lock.yaml`, #6008); the one hand edit is removing the entries of a test you deleted, which a report cannot see.
- [ ] Weak specs — `pnpm run test:weak` (`auralis-web/frontend/scripts/check-weak-tests.mjs`, #5682, df07edcd7; baseline empty, a step in `frontend-test.yml`) lists specs with no assertion or only presence checks (`toBeDefined` / `toBeTruthy` / `not.toBeNull`); a new spec that trips it is a finding.
- [ ] Memory — the suite needs the 2GB-heap runner (`pnpm run test:memory`); flag any new spec that spins an unbounded mock loop.
- [ ] Mock correctness — do mocks (`vi.*`) accurately represent real behavior? Over-mocking? Every `vi.mock` string must resolve to an existing module (`auralis-web/frontend/src/tests/vi-mock-targets-exist.test.ts`, #5678): a mock of a moved or deleted module silently mocks nothing. Specs for error paths must assert the failure, not pass on the initial null (#5674). The MSW `onUnhandledRequest` in `auralis-web/frontend/src/test/setup.ts` records an unmatched `/api` call (`auralis-web/frontend/src/test/unhandledRequests.ts`) and fails the test in `afterEach` (#5681, bb72d3e1e; pinned by `auralis-web/frontend/src/test/__tests__/mswUnhandled.5681.test.ts`); a REST endpoint a spec reaches needs a default handler in `auralis-web/frontend/src/test/mocks/handlers.ts`, and a spec that clears the list to opt out (only `useRestAPI.test.ts` does) is a finding unless it stubs `fetch` itself.
- [ ] Async testing — are async operations properly awaited? Any floating promises in tests?
- [ ] User interaction testing — are tests using `@testing-library` user events, not direct DOM manipulation?
- [ ] Snapshot overuse — are snapshots testing the right thing, or just freezing implementation details?
- [ ] Edge cases — empty states, error states, loading states, large data sets?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/auralis/frontend`
3. Fetch dedup baseline: the canonical dump from `_audit-common.md` Deduplication step 1 (`--limit 100000` + truncation assertion), redirected to `/tmp/audit/auralis/frontend/issues.json`
4. Scan `docs/audits/` for prior frontend audit reports

## Phase 2: Launch Dimension Agents

Launch one Agent-tool subagent per dimension (max 3 concurrent). Each agent writes its output to `/tmp/audit/auralis/frontend/dim_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/auralis/frontend/issues.json`
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Component Quality | Redux State | Hook Correctness | Type Safety | Design System | API Client | Performance | Accessibility | Test Coverage
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet demonstrating the issue
- **Impact**: What breaks, when, user-visible effect
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Dimension → Output mapping:
- Dimension 1 (Component Quality) → `/tmp/audit/auralis/frontend/dim_1.md`
- Dimension 2 (Redux State) → `/tmp/audit/auralis/frontend/dim_2.md`
- Dimension 3 (Hook Correctness) → `/tmp/audit/auralis/frontend/dim_3.md`
- Dimension 4 (Type Safety) → `/tmp/audit/auralis/frontend/dim_4.md`
- Dimension 5 (Design System) → `/tmp/audit/auralis/frontend/dim_5.md`
- Dimension 6 (API Client) → `/tmp/audit/auralis/frontend/dim_6.md`
- Dimension 7 (Performance) → `/tmp/audit/auralis/frontend/dim_7.md`
- Dimension 8 (Accessibility) → `/tmp/audit/auralis/frontend/dim_8.md`
- Dimension 9 (Test Coverage) → `/tmp/audit/auralis/frontend/dim_9.md`

## Phase 3: Merge

1. Read all `/tmp/audit/auralis/frontend/dim_*.md` files
2. Combine into `docs/audits/AUDIT_FRONTEND_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most impactful issues
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across dimensions
   - **Relationships** — How findings interact, shared root causes
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-dimension duplicates (same file:line found by multiple dimensions)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/auralis/frontend`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_FRONTEND_<TODAY>.md`

## Labels

Use labels when publishing: severity label + `frontend` + `bug`
