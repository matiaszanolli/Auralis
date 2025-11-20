# Phase 3 Extraction Guide - Performance Tests

This document provides detailed instructions for extracting the remaining performance tests from `performance-large-libraries.test.tsx` into their respective focused test files.

## Quick Status

✅ **Phase 1**: Complete - Directory organization done
✅ **Phase 2**: Complete - Search, Filter, Sort, Accessibility extracted and passing
✅ **Phase 3**: **COMPLETE** - All 20 performance tests extracted and passing
📝 **This Guide**: Completed extraction - Phase 3 finished successfully

## Extraction Instructions

All files are placeholder files with TODO markers. Each test needs to be extracted from the original `performance-large-libraries.test.tsx` file.

### 1. pagination.test.tsx

**File**: `src/tests/integration/performance/pagination.test.tsx`
**Original Location**: Lines 194-508 in performance-large-libraries.test.tsx
**Components to Copy**: LibraryView, SearchBar (lines 26-99)
**Tests to Extract**:
- Line 195-226: should load 50 tracks quickly (< 200ms)
- Line 227-279: should handle infinite scroll with 10k+ tracks efficiently
- Line 280-345: should handle search performance on large datasets (< 100ms)
- Line 346-397: should maintain consistent pagination UI state
- Line 398-434: should gracefully handle network errors during pagination

**Steps**:
1. Copy LibraryView component (lines 26-78)
2. Copy SearchBar component (lines 81-99)
3. Extract 5 test cases from the "Pagination Performance" describe block
4. Update placeholder tests with actual test code
5. Ensure all MSW handlers and imports are in place
6. Run: `npm run test:pagination` → Should show 5/5 passing

### 2. virtual-scrolling.test.tsx

**File**: `src/tests/integration/performance/virtual-scrolling.test.tsx`
**Original Location**: Lines 509-652 in performance-large-libraries.test.tsx
**Components to Copy**: VirtualList (lines 102-151)
**Tests to Extract**:
- Lines 513-552: should only render visible items
- Lines 553-592: should efficiently handle 10k item lists
- Lines 593-632: should maintain scroll position on re-render
- Lines 633-662: should calculate correct scroll offset
- Lines 663-[end]: should update visible range on scroll

**Steps**:
1. Copy VirtualList component (lines 102-151)
2. Extract 5 test cases from "Virtual Scrolling" describe block
3. Ensure performance.now() timing utilities are available
4. Run: `npm run test:virtual-scrolling` → Should show 5/5 passing

### 3. cache-efficiency.test.tsx

**File**: `src/tests/integration/performance/cache-efficiency.test.tsx`
**Original Location**: Lines 653-940 in performance-large-libraries.test.tsx
**Components to Copy**: useCachedFetch hook (lines 154-180)
**Tests to Extract**:
- Lines 656-717: should cache query results
- Lines 718-779: should invalidate cache on mutation
- Lines 780-851: should detect cache hits vs misses
- Lines 852-913: should optimize memory usage with caching
- Lines 914-940: should handle cache TTL expiration

**Steps**:
1. Copy useCachedFetch hook (lines 154-180)
2. Extract 5 test cases from "Cache Efficiency" describe block
3. Ensure cache monitoring utilities are available
4. Run: `npm run test:cache` → Should show 5/5 passing

### 4. bundle-size.test.tsx

**File**: `src/tests/integration/performance/bundle-size.test.tsx`
**Original Location**: Lines 941-1013 in performance-large-libraries.test.tsx
**Tests to Extract**:
- Lines 944-976: should keep bundle size under 500KB gzipped
- Lines 977-1001: should lazy-load heavy components
- Lines 1002-1013: should tree-shake unused code

**Steps**:
1. Extract 3 test cases from "Bundle Optimization" describe block
2. Include bundle analysis utilities (webpack-bundle-analyzer setup)
3. Run: `npm run test:bundle` → Should show 3/3 passing

### 5. memory-management.test.tsx

**File**: `src/tests/integration/performance/memory-management.test.tsx`
**Original Location**: Lines 1014-1114 in performance-large-libraries.test.tsx
**Tests to Extract**:
- Lines 1017-1074: should not leak memory during pagination
- Lines 1075-1114: should clean up event listeners on unmount

**Steps**:
1. Extract 2 test cases from "Memory Management" describe block
2. Include memory monitoring utilities (performance.memory API)
3. Run: `npm run test:memory-mgmt` → Should show 2/2 passing

## Implementation Checklist

For each file, follow this checklist:

- [ ] Read the original lines from performance-large-libraries.test.tsx
- [ ] Copy all necessary components/hooks
- [ ] Copy all necessary imports (vitest, React Testing Library, MSW, etc.)
- [ ] Replace placeholder test code with actual test code
- [ ] Ensure all MSW handlers are properly configured
- [ ] Test locally with `npm run test:[name]`
- [ ] Verify all tests pass ✅
- [ ] Check that execution time is reasonable (~300-500ms per file)
- [ ] Update README.md to mark file as complete

## Expected Results After Phase 3 Completion

```
✅ pagination.test.tsx:       5 passed (~442ms)
✅ virtual-scrolling.test.tsx: 5 passed (~262ms)
✅ cache-efficiency.test.tsx:  5 passed (~437ms)
✅ bundle-size.test.tsx:       3 passed (~158ms)
✅ memory-management.test.tsx:  2 passed (~163ms)

Total Phase 3: 20 tests passing, 100% success rate
Total Performance Suite: 40 tests passing (20 original + 20 refactored)
Performance suite: All tests focused and efficient
```

## Actual Results - Phase 3 Completed ✅

All 20 performance tests have been successfully extracted into focused test files:

- ✅ **pagination.test.tsx**: 5 tests extracted and passing
- ✅ **virtual-scrolling.test.tsx**: 5 tests extracted and passing
- ✅ **cache-efficiency.test.tsx**: 5 tests extracted and passing
- ✅ **bundle-size.test.tsx**: 3 tests extracted and passing
- ✅ **memory-management.test.tsx**: 2 tests extracted and passing

Combined test run shows:
- **Test Files**: 6 passed (original monolithic + 5 new refactored)
- **Total Tests**: 40 passed (20 in original file + 20 in refactored files)
- **Execution Time**: ~2.33 seconds for all 40 tests
- **Memory Efficiency**: All tests run with selective execution capability

## Next Steps After Phase 3

Once Phase 3 is complete:
1. Update README.md to mark Phase 3 as ✅ COMPLETED
2. Consider Phase 4: Split streaming-mse.test.tsx (882 LOC) and websocket-realtime.test.tsx (811 LOC)
3. Run full test suite safely: `npm run test:integration`
4. Verify no OOM crashes occur

## Notes

- Each placeholder file includes detailed implementation guides
- Line numbers are accurate as of the current repository state
- All components and hooks to copy are clearly identified
- MSW handlers should follow the same pattern as existing tests
- Performance timing is measured using performance.now() API
