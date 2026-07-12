# Incremental Audit — 2026-03-25

**Range**: `HEAD~10..HEAD` (10 commits)
**Files changed**: 16 (all frontend)
**Auditor**: Claude Opus 4.6 (automated)

## Change Summary

All 10 commits are fixes for issues filed in the 2026-03-25 frontend and concurrency audits:

| Commit | Issue | Change |
|--------|-------|--------|
| `4df0133d` | #3371 | Add aria-label to SearchBar input |
| `c89285ac` | #3381 | Gate console.log behind DEBUG flag, remove useMemo side effect |
| `965bf135` | #3384 | Tighten useOptimisticUpdate generic from `any[]` to `unknown[]` |
| `ed47ba63` | #3373 | Key resume position getters by stream type to prevent race |
| `af65e106` | #3413 | Stabilize onToggleSelect prop for SelectableTrackRow memo |
| `b759d0ea` | #3387 | Split StarfieldBackground and StreamingErrorBoundary under 300 lines |
| `ddd17921` | #3380 | Replace local connection state with Redux connectionSlice |
| `bd5c19c2` | — | Replace double-cast with isWebSocketErrorMessage type guard |
| `85e188e2` | #3391 | Populate empty auto-hide timer callback in ConnectionStatusIndicator |
| `8bfcabc2` | #3386 | Add role=alert to QueuePanel error banner |

## High-Risk Changes

None of the changes touch audio core, player engine, backend streaming, or database. All are frontend-only.

### `ed47ba63` — Resume position getter keying (#3373)

**Risk**: MEDIUM — Changes WebSocket reconnection behavior.

**Review**: The fix correctly replaces the singleton `singletonResumePositionGetter` with a `Record<string, () => number>` keyed by stream type (`'play_enhanced'` or `'play_normal'`). On reconnect, the getter is looked up by `singletonLastStreamCommand.type`, which matches the key written by the active play hook.

**Potential issue**: The `resetWebSocketSingletons()` test helper uses `for..in` + `delete` to clear the record. This is correct but unconventional — `Object.keys().forEach(k => delete obj[k])` is more idiomatic. No functional impact.

**Verdict**: Clean fix. No new bugs introduced.

### `ddd17921` — ConnectionStatusIndicator → Redux (#3380)

**Risk**: MEDIUM — Refactors component state management.

**Review**: Removes the local `ConnectionStatus` interface and `useState`, replaces with `useConnectionState()` from Redux. Health polling now dispatches `setAPIConnected()` and `setLatency()` to Redux. Auto-hide timer callback now properly calls `setShowDetails(false)`.

**Potential issue**: `useEffect` dep array changed from `[]` to `[dispatch]` for the health polling effect. `dispatch` identity is stable in Redux, so this is safe. The derived `isReconnecting` is now computed inline instead of stored — correct.

**Minor**: `status.lastError` was previously `Error | null`, now it's `string | null` (from Redux slice). The template accesses `status.lastError.message` → `status.lastError` directly. Correct — the component was previously displaying `status.lastError.message` but now correctly displays the string directly.

**Verdict**: Clean refactor. No new bugs.

### `af65e106` — Stabilize onToggleSelect (#3413)

**Risk**: LOW-MEDIUM — Changes prop signature of SelectableTrackRow.

**Review**: `onToggleSelect` prop changed from `(event: React.MouseEvent) => void` to `(trackId: number, event: React.MouseEvent) => void`. Inside SelectableTrackRow, a `useCallback` binds `track.id` to produce a stable `boundToggleSelect`. TrackListViewContent passes the parent `onToggleSelect` directly instead of wrapping in an inline arrow.

**Potential issue**: The `SelectableTrackRow.test.tsx` file was also updated — verified it now tests with the new signature.

**Verdict**: Clean fix. Correctly stabilizes the callback chain.

### `b759d0ea` — Component split (#3387)

**Risk**: LOW — Extracts code to sibling files, no logic changes.

**Review**: StarfieldBackground's GLSL shaders moved to `starfield.shaders.ts`. StreamingErrorBoundary's styles, enums, and helper functions moved to `StreamingErrorBoundary.styles.ts`. Both files are re-exported from the original modules.

**Potential issue**: `StreamingErrorType` and `ErrorSeverity` enums are now exported from both `.styles.ts` and re-exported from the main file. Could cause confusion about canonical import path, but no functional issue.

**Verdict**: Clean extraction. No behavior changes.

## Findings

### INC-01: WebSocketContext.resetWebSocketSingletons clears getters via for..in delete — fragile pattern
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx` (commit: `ed47ba63`)
- **Status**: NEW
- **Description**: `for (const key in singletonResumePositionGetters) { delete ... }` works but is sensitive to prototype pollution and less readable than `Object.keys().forEach()`. Minor test-only concern.
- **Impact**: None in production. Could cause test leakage if prototype is polluted.
- **Suggested Fix**: Replace with `for (const key of Object.keys(singletonResumePositionGetters))`.

### INC-02: StreamingErrorBoundary.styles.ts and StreamingErrorBoundary.tsx both export StreamingErrorType enum
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/components/enhancement/StreamingErrorBoundary.tsx` (commit: `b759d0ea`)
- **Status**: NEW
- **Description**: `StreamingErrorType` and `ErrorSeverity` are defined in `.styles.ts` and re-exported from the main file via `export { StreamingErrorType, ErrorSeverity }`. Consumers may import from either path. No bundle impact (tree-shaking handles it), but creates two valid import paths.
- **Impact**: Developer confusion. No runtime impact.
- **Suggested Fix**: Document canonical import path, or only export from main file.

## Cross-Layer Impact

No cross-layer impacts. All changes are frontend-only and don't alter any API contracts, WebSocket message formats, or backend behavior.

## Missing Tests

| Change | Test Status |
|--------|------------|
| `ed47ba63` — resume position keying | `resetWebSocketSingletons` updated. No new reconnect test added for the keyed-getter behavior. |
| `ddd17921` — Redux connection state | No test update for ConnectionStatusIndicator dispatching to Redux. |
| `af65e106` — SelectableTrackRow signature | Test file updated ✓ |
| `b759d0ea` — component split | No tests needed (pure extraction) |
| All others | One-line fixes, no new test surface needed |

### INC-03: No integration test for keyed resume position getter behavior
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/contexts/WebSocketContext.tsx` (commit: `ed47ba63`)
- **Status**: NEW
- **Description**: The fix correctly keys getters by stream type, but there's no test verifying that on reconnect, the correct getter is called for the active stream type.
- **Impact**: Regression risk if reconnect logic changes.
- **Suggested Fix**: Add a test that mounts both play hooks, triggers reconnect, and asserts the getter for the active stream type is called.

---

*Report generated by Claude Opus 4.6 — 2026-03-25*
*All 10 commits are clean fixes with no new bugs introduced. 3 LOW findings (test/style).*
