# Frontend Audit

Audit the Auralis React frontend for component quality, state management bugs, hook correctness, type safety, design system adherence, accessibility gaps, performance issues, and test coverage. Then create GitHub issues for every new confirmed finding.

## Scope

This audit covers ONLY the frontend code:

- **Components**: `auralis-web/frontend/src/components/`
- **Hooks**: `auralis-web/frontend/src/hooks/` (player, library, enhancement, websocket, api, app, fingerprint, shared)
- **Store**: `auralis-web/frontend/src/store/` (Redux slices, selectors, middleware)
- **Services**: `auralis-web/frontend/src/services/` (API clients)
- **Design System**: `auralis-web/frontend/src/design-system/` (tokens, theme)
- **Tests**: `auralis-web/frontend/src/test/` and co-located test files
- **Config**: `auralis-web/frontend/vite.config.*`, `tsconfig.json`, `package.json`

Out of scope: Python backend, audio engine, Rust DSP, database.

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Data loss, audio playback failure, or exploitable XSS in production NOW. | Dropped audio frames from WebSocket, unescaped metadata rendering, Redux state corruption causing crash |
| **HIGH** | Broken UX under realistic conditions. Fix before next release. | Stale closure causing wrong track to play, WebSocket reconnect losing state, memory leak in audio hooks |
| **MEDIUM** | Incorrect behavior with workarounds, or affects non-critical paths. | Missing error boundary, inconsistent loading states, hardcoded colors bypassing design tokens |
| **LOW** | Code quality, maintainability, or minor inconsistencies. | Component exceeding 300 lines, missing type annotations, dead imports, undocumented props |

## Audit Dimensions

### Dimension 1: Component Quality

**Key locations**: `auralis-web/frontend/src/components/`

**Check**:
- [ ] Single responsibility — does each component do ONE thing? Are any > 300 lines?
- [ ] Prop drilling — are props passed through > 2 intermediate components instead of using context or Redux?
- [ ] Conditional rendering — any branches that produce inconsistent DOM structure causing React reconciliation issues?
- [ ] Key usage in lists — stable keys derived from data, never array indices for reorderable lists?
- [ ] Ref usage — are refs used correctly for imperative operations (audio elements, scroll, focus)?
- [ ] Error boundaries — are they wrapping critical subtrees (player, library, enhancement)?
- [ ] Unmounted component updates — do async operations check component mount state before setState?

### Dimension 2: Redux State Management

**Key locations**: `auralis-web/frontend/src/store/`

**Check**:
- [ ] Slice design — is state normalized? Are there duplicated pieces of state that can go out of sync?
- [ ] Selector memoization — are selectors using `createSelector` where derived data is computed? Any selectors returning new references on every call?
- [ ] Dispatch ordering — can rapid dispatches (skip, skip, skip) leave the store in an inconsistent intermediate state?
- [ ] Thunk / async action error handling — are rejected promises caught and dispatched as error states?
- [ ] Middleware — any custom middleware that could drop or reorder actions?
- [ ] State shape — are there deeply nested objects that make immutable updates error-prone?
- [ ] Serializable state — are non-serializable values (functions, class instances, Promises) stored in Redux?

### Dimension 3: Hook Correctness

**Key locations**: `auralis-web/frontend/src/hooks/`

**Check**:
- [ ] Dependency arrays — missing deps causing stale closures? Excess deps causing infinite re-renders?
- [ ] `useEffect` cleanup — do WebSocket hooks close connections? Do timers get cleared? Do subscriptions unsubscribe?
- [ ] `useCallback` / `useMemo` — are expensive computations memoized? Are callback identities stable for child components?
- [ ] Custom hook return stability — do hooks return the same reference shape on every render?
- [ ] Race conditions — can an effect fire with outdated closure values after rapid state changes?
- [ ] WebSocket hooks (`hooks/websocket/`) — reconnection logic, message queue during disconnect, binary frame parsing
- [ ] Player hooks (`hooks/player/`) — do they correctly synchronize with backend playback state? Stale position/duration?
- [ ] API hooks (`hooks/api/`) — cancellation of in-flight requests on unmount? Deduplication of concurrent identical requests?

### Dimension 4: TypeScript Type Safety

**Key locations**: All `.ts` and `.tsx` files under `auralis-web/frontend/src/`

**Check**:
- [ ] `any` usage — are there `any` types that bypass safety? Should they be `unknown` or properly typed?
- [ ] Type assertions (`as`) — are there unsafe casts that could mask runtime errors?
- [ ] API response types — do they match the actual backend response schemas in `auralis-web/backend/schemas.py`?
- [ ] WebSocket message types — are binary and text message types correctly discriminated?
- [ ] Event handler types — are DOM event types correctly specified?
- [ ] Union exhaustiveness — are switch/if chains over union types exhaustive (use `never` checks)?
- [ ] Generic constraints — are generic hooks and utilities properly constrained?

### Dimension 5: Design System Adherence

**Key locations**: `auralis-web/frontend/src/design-system/`, all component style files

**Check**:
- [ ] Token usage — are ALL colors sourced from `import { tokens } from '@/design-system'`? Any hardcoded hex/rgb values?
- [ ] Spacing — consistent use of spacing tokens vs arbitrary pixel values?
- [ ] Typography — font sizes, weights, line heights from tokens?
- [ ] Responsive — do components use responsive breakpoints from the design system?
- [ ] Dark/light theme — do all styled elements respect the theme context?
- [ ] Import paths — all using `@/` absolute imports, no relative `../../` paths?

### Dimension 6: API Client & Data Fetching

**Key locations**: `auralis-web/frontend/src/services/`

**Check**:
- [ ] Error handling — are HTTP errors (4xx, 5xx) caught and surfaced to the UI?
- [ ] Loading states — is there a loading indicator for every async operation?
- [ ] Request cancellation — are fetch/axios requests cancelled on component unmount?
- [ ] Retry logic — are transient failures (network, 503) retried? Are non-transient failures (400, 404) NOT retried?
- [ ] Response validation — is the response shape validated or trusted blindly?
- [ ] Base URL configuration — is the API base URL configurable, not hardcoded?
- [ ] camelCase/snake_case — is the casing conversion between frontend (camelCase) and backend (snake_case) handled consistently?

### Dimension 7: Performance

**Key locations**: All component and hook files

**Check**:
- [ ] Unnecessary re-renders — are components re-rendering when their props haven't changed? Missing `React.memo`?
- [ ] Large list rendering — are lists with 100+ items virtualized?
- [ ] Bundle size — are there large dependencies that could be lazy-loaded or tree-shaken?
- [ ] Image optimization — are artwork images lazy-loaded? Proper sizing?
- [ ] WebSocket message rate — can high-frequency messages (position updates) flood React renders?
- [ ] Audio buffer memory — are Web Audio API buffers released when tracks change?
- [ ] Effect cascades — does one state change trigger a chain of effects that could be batched?

### Dimension 8: Accessibility

**Key locations**: All component files

**Check**:
- [ ] Keyboard navigation — can all interactive elements be reached and activated via keyboard?
- [ ] ARIA labels — do custom controls (sliders, progress bars, play/pause) have proper ARIA attributes?
- [ ] Focus management — is focus correctly managed after modal open/close, route changes, and dynamic content?
- [ ] Screen reader — are player state changes (now playing, paused) announced?
- [ ] Color contrast — do text and interactive elements meet WCAG AA contrast ratios?
- [ ] Semantic HTML — are headings hierarchical? Are lists using `<ul>`/`<ol>`? Are buttons vs links correct?

### Dimension 9: Test Coverage

**Key locations**: `auralis-web/frontend/src/test/`, co-located `*.test.*` files

**Check**:
- [ ] Critical path coverage — are player hooks, WebSocket hooks, and Redux slices tested?
- [ ] Mock correctness — do mocks (`vi.*`) accurately represent real behavior? Over-mocking?
- [ ] Async testing — are async operations properly awaited? Any floating promises in tests?
- [ ] User interaction testing — are tests using `@testing-library` user events, not direct DOM manipulation?
- [ ] Snapshot overuse — are snapshots testing the right thing, or just freezing implementation details?
- [ ] Edge cases — empty states, error states, loading states, large data sets?

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip
   - **CLOSED**: Verify fix is in place. If regressed, report as "Regression of #NNN"
4. If no match: Report as NEW

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_FRONTEND_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

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

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + `frontend` + `bug`
   - **Body**:
     ```
     ## Summary
     <description>

     ## Evidence / Code Paths
     - **File**: `<path>:<line-range>`
     - **Code**: <relevant snippet>

     ## Impact
     - **Severity**: <SEVERITY>
     - **What breaks**: <failure mode>
     - **User-visible effect**: <what the user sees>

     ## Related Issues
     - #NNN — <relationship>

     ## Proposed Fix
     <recommended approach>

     ## Acceptance Criteria
     - [ ] <criterion>

     ## Test Plan
     - <test description> — assert <expected>
     ```

2. **Cross-reference**: For each new issue that relates to an existing issue:
   ```
   gh issue comment <EXISTING_ISSUE> --body "Related: #<NEW_ISSUE> — <brief description>"
   ```

3. **Print a summary table** at the end:
   ```
   | Finding | Severity | Dimension | Action | Issue |
   |---------|----------|-----------|--------|-------|
   | <title> | HIGH | Hook Correctness | CREATED | #NNN |
   | <title> | MEDIUM | Redux State | DUPLICATE of #NNN | — |
   ```
