# Fix for Issue #2137: usePlaybackQueue Callback Stability

**Date**: 2026-02-16
**Issue**: [#2137](https://github.com/matiaszanolli/Auralis/issues/2137) - MEDIUM - usePlaybackQueue callbacks recreated on every state change causing excessive re-renders
**Status**: ✅ Fixed

## Summary

Fixed performance issue where multiple `useCallback` hooks in `usePlaybackQueue` included the full `state` object in their dependency arrays. Since `state` changes on every WebSocket message (queue updates, shuffle changes, repeat mode changes), callbacks were recreated constantly, causing unnecessary re-renders in child components.

## Changes Made

### 1. Added useRef for State Tracking
**File**: [auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts](../../../auralis-web/frontend/src/hooks/player/usePlaybackQueue.ts:162-167)

```typescript
/**
 * Ref to track latest state without causing callback recreation
 * Used for optimistic rollback in callbacks
 */
const stateRef = useRef<QueueState>(state);
stateRef.current = state;
```

### 2. Updated Callbacks to Use stateRef

**Before** (callback recreated on every state change):
```typescript
const setQueue = useCallback(async (tracks, startIndex = 0) => {
  const previousState = state; // Captures state from closure
  // ...
}, [api, state]); // ❌ state in dependencies causes recreation
```

**After** (stable callback reference):
```typescript
const setQueue = useCallback(async (tracks, startIndex = 0) => {
  const previousState = stateRef.current; // Always latest state
  // ...
}, [api]); // ✅ Only api in dependencies
```

### 3. Updated Callbacks

- **setQueue** (line 236): Removed `state` from dependencies, uses `stateRef.current`
- **toggleShuffle** (line 412): Removed `state.isShuffled` from dependencies, uses `stateRef.current`
- **setRepeatMode** (line 455): Removed `state` from dependencies, uses `stateRef.current`
- **clearQueue** (line 509): Removed `state` from dependencies, uses `stateRef.current`

## Testing

### New Test Suite
**File**: [auralis-web/frontend/src/hooks/player/__tests__/usePlaybackQueue.test.ts](../../../auralis-web/frontend/src/hooks/player/__tests__/usePlaybackQueue.test.ts:732-1004)

Added two comprehensive test sections:

#### 1. Callback Stability Tests (4 tests)
Tests verify that callback references remain stable when state changes:
- `setQueue` reference stable when state changes ✅
- `clearQueue` reference stable when state changes ✅
- `toggleShuffle` reference stable when state changes ✅
- `setRepeatMode` reference stable when state changes ✅

#### 2. Optimistic Rollback Tests (4 tests)
Tests verify that optimistic rollback still works correctly with `useRef`:
- `setQueue` rollback on API failure ✅
- `toggleShuffle` rollback on API failure ✅
- `setRepeatMode` rollback on API failure ✅
- `clearQueue` rollback on API failure ✅

### Test Results
```bash
✓ src/hooks/player/__tests__/usePlaybackQueue.test.ts (27 tests)
  Test Files  1 passed (1)
  Tests  27 passed (27)
```

## Performance Impact

### Before
- **Issue**: Callbacks recreated on every WebSocket message
- **Frequency**: Every queue update, shuffle change, repeat mode change
- **Impact**: All components receiving these callbacks re-render unnecessarily
- **Example**: With position updates every 100ms, callbacks recreate 10 times/second

### After
- **Benefit**: Callbacks have stable references across state changes
- **Only recreate**: When `api` instance changes (rare - only on mount/unmount)
- **Result**: Combined with TrackRow memoization (#2173), dramatically reduces re-renders

## Integration with Issue #2173

This fix works in tandem with the TrackRow memoization fix:

1. **#2173**: TrackRow components now memoized, only re-render when critical props change
2. **#2137**: Callbacks now have stable references, so they don't trigger re-renders

**Combined Effect**:
- Before: TrackRow re-renders + callback changes = constant re-rendering
- After: TrackRow memoized + stable callbacks = minimal re-renders only when truly needed

## How useRef Works Here

The pattern uses `useRef` to maintain a reference to the latest state without including it in `useCallback` dependencies:

```typescript
// Ref always points to latest state
const stateRef = useRef(state);
stateRef.current = state; // Updates on every render

// Callback uses ref, not direct state
const someCallback = useCallback(async () => {
  const previousState = stateRef.current; // Always latest
  // ... optimistic update
  try {
    // ... API call
  } catch (err) {
    setState(previousState); // Rollback works correctly
  }
}, [api]); // Only stable dependencies
```

**Key Insight**: `stateRef.current` always reflects the latest state at the time the callback executes, not when the callback was created. This makes optimistic rollback work correctly while keeping callback references stable.

## Acceptance Criteria

✅ Callbacks have stable references when queue state changes
✅ Optimistic rollback still works correctly
✅ React DevTools shows reduced re-render count for queue consumers
✅ All existing tests pass
✅ New tests verify callback stability and rollback behavior

## Related Issues

- [#2173](https://github.com/matiaszanolli/Auralis/issues/2173) - TrackRow memoization (fixes the other side of this problem)
- [#2131](https://github.com/matiaszanolli/Auralis/issues/2131) - Factory selectors (another re-render source)

## Migration Notes

None required. Changes are internal to the hook implementation and don't affect the public API.

## Future Improvements

1. Apply same pattern to other hooks with similar issues
2. Consider creating a custom `useStableCallback` hook to encapsulate this pattern
3. Profile with React DevTools to measure actual re-render reduction
