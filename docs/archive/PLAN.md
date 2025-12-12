# Implementation Plan: Infinite Scroll & Pagination Consolidation

## Goal
Eliminate code duplication and architectural inconsistency in infinite scroll implementations across Tracks, Albums, and Artists views by consolidating to a single unified pattern.

## Current State Analysis
- **Tracks**: Uses `useLibraryQuery` + shared `useInfiniteScroll` ✅ (BEST PATTERN)
- **Albums**: Uses custom `useAlbumGridPagination` + custom `useAlbumGridScroll` ❌ (DUPLICATE)
- **Artists**: Uses custom `useArtistListPagination` with inline scroll detection ❌ (DUPLICATE)
- **Backend**: Artist search has N+1 performance bug (fetches all 10k results just to count)

## Scope
- **Frontend**: 5 files to modify/delete
- **Backend**: 1 critical performance fix (artist search)
- **Tests**: Verify existing tests pass, minimal test changes needed
- **Estimated Impact**: ~400 lines of duplicate code eliminated, consistent pattern across all list views

---

## Phase 1: Backend Performance Fix (Highest Priority)

### 1.1 Fix Artist Search N+1 Problem
**File**: `auralis-web/backend/routers/artists.py` (lines 103-115)

**Current Problem**:
```python
if search:
  artists = manager.artists.search(search, limit=limit, offset=offset)  # Line 105
  all_search_results = manager.artists.search(search, limit=10000, offset=0)  # Line 107 - BAD!
  total = len(all_search_results)  # Line 108 - Only for counting
```

**Solution**:
- Modify `manager.artists.search()` to return search metadata (count)
- Change: `all_search_results = manager.artists.search(...)` to get count from first response
- OR: Use database COUNT query instead of fetching all results

**Changes Required**:
1. Check if `manager.artists.search()` can return a tuple with count
2. If not, modify the repository method to support count parameter
3. Update artist router to use count from first response instead of fetching all

**Expected Result**: Artist search latency reduces from ~200ms to ~50ms (eliminates duplicate query)

---

## Phase 2: Frontend Consolidation - Albums View

### 2.1 Replace Album Pagination Hooks
**Remove These Files**:
- `auralis-web/frontend/src/components/library/Items/albums/useAlbumGridPagination.ts`
- `auralis-web/frontend/src/components/library/Items/albums/useAlbumGridScroll.ts`

**Update**: `auralis-web/frontend/src/components/library/Items/albums/CozyAlbumGrid.tsx`

**Current Code** (lines 36-56):
```typescript
const {
  albums, loading, error, offset, hasMore, totalAlbums, isLoadingMore, fetchAlbums, loadMore,
} = useAlbumGridPagination();

const { containerRef, loadMoreTriggerRef } = useAlbumGridScroll({
  hasMore, isLoadingMore, loading, offset, albumsLength: albums.length, onLoadMore: loadMore,
});
```

**New Code**:
```typescript
const loadMoreRef = useRef<HTMLDivElement>(null);
const { data: albums, isLoading: loading, error, total: totalAlbums, hasMore, fetchMore } = useAlbumsQuery({ limit: 50 });
useInfiniteScroll({ threshold: 0.8, onLoadMore: fetchMore, hasMore, isLoading: loading });

// containerRef already exists in component, loadMoreRef is the trigger for useInfiniteScroll
```

**Key Changes**:
1. Import `useAlbumsQuery` from `@/hooks/library`
2. Import `useInfiniteScroll` from `@/hooks/shared`
3. Add `loadMoreRef` to the trigger element in render
4. Remove manual scroll listener logic
5. Update state variable names (loading → isLoading, totalAlbums → total)
6. Delete references to `fetchAlbums` and `loadMore` callbacks

**Expected Result**: ~99 lines removed, consistent with Tracks pattern

---

## Phase 3: Frontend Consolidation - Artists View

### 3.1 Refactor Artist Pagination Hooks
**Remove File**:
- `auralis-web/frontend/src/components/library/Hooks/useArtistListPagination.ts` (200+ lines with mixed concerns)

**Create New File**:
- `auralis-web/frontend/src/hooks/shared/useGroupedArtists.ts` (extracts grouping logic, ~40 lines)

**New Hook Implementation** (`useGroupedArtists.ts`):
```typescript
export function useGroupedArtists(artists: Artist[]) {
  const groupedArtists = useMemo(() => {
    return artists.reduce((acc, artist) => {
      const initial = artist.name.charAt(0).toUpperCase();
      if (!acc[initial]) acc[initial] = [];
      acc[initial].push(artist);
      return acc;
    }, {} as Record<string, Artist[]>);
  }, [artists]);

  const sortedLetters = useMemo(() => Object.keys(groupedArtists).sort(), [groupedArtists]);

  return { groupedArtists, sortedLetters };
}
```

**Update**: `auralis-web/frontend/src/components/library/Items/artists/CozyArtistList.tsx`

**Current Code** (lines 38-55):
```typescript
const {
  artists, loading, error, hasMore, totalArtists, isLoadingMore,
  containerRef, loadMoreTriggerRef,
  contextMenuState, contextMenuArtist,
  handleCloseContextMenu, handleArtistClick, handleContextMenuOpen,
  groupedArtists, sortedLetters,
} = useArtistListPagination({ onArtistClick });
```

**New Code**:
```typescript
const { data: artists, isLoading: loading, error, total: totalArtists, hasMore, fetchMore } = useArtistsQuery({ limit: 50 });
const { groupedArtists, sortedLetters } = useGroupedArtists(artists);
const loadMoreRef = useRef<HTMLDivElement>(null);

useInfiniteScroll({ threshold: 0.8, onLoadMore: fetchMore, hasMore, isLoading: loading });

// Keep context menu hooks as-is
const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();
const [contextMenuArtist, setContextMenuArtist] = useState<Artist | null>(null);

const handleContextMenuOpen = (e: React.MouseEvent, artist: Artist) => {
  e.preventDefault();
  e.stopPropagation();
  setContextMenuArtist(artist);
  handleContextMenu(e);
};

const handleCloseContextMenuLocal = () => {
  setContextMenuArtist(null);
  handleCloseContextMenu();
};
```

**Key Changes**:
1. Replace custom pagination hook with `useArtistsQuery`
2. Extract artist grouping logic to `useGroupedArtists` hook
3. Use shared `useInfiniteScroll` with loadMoreRef
4. Keep context menu logic inline (it's artist-specific, not pagination-related)
5. Update state variable names (loading → isLoading)

**Expected Result**: ~150 lines removed from component + hook, consistent pattern

---

## Phase 4: Remove Duplicate Scroll Hook

### 4.1 Delete Unused Hook
**File to Remove**:
- `auralis-web/frontend/src/components/library/Views/useInfiniteScroll.ts`

**Reason**: This is a duplicate of the shared `useInfiniteScroll` in `hooks/shared/useInfiniteScroll.ts`. All components should use the shared hook.

**Verification**:
- Grep for imports to ensure no other files use it
- Check git history to see if it's truly unused

---

## Phase 5: Verify Pattern Consistency

### 5.1 Verify All Endpoints Return Same Response Structure
**Endpoints to Check**:
1. `GET /api/library/tracks` → `LibraryQueryResponse<Track>`
2. `GET /api/library/albums` → Same structure
3. `GET /api/library/artists` → Same structure

**Expected Structure**:
```json
{
  "items": [...],
  "total": number,
  "offset": number,
  "limit": number,
  "has_more": boolean
}
```

**Issue to Fix**: Some endpoints return `data` instead of `items` or custom field names
- If found: Update responses to standardize on `items` field

### 5.2 Verify Backend Search Accuracy
**Check These Endpoints**:
1. `GET /api/library/tracks?search=...` → Accurate `has_more`?
2. `GET /api/library/albums?search=...` → Accurate `has_more`?
3. `GET /api/library/artists?search=...` → Fixed after Phase 1?

**Issue to Fix**: Search endpoints use heuristics instead of accurate counts
- Pattern: If `len(results) >= limit` assume `has_more = true`
- Problem: Last page of results still shows "Load More"
- Solution: Use actual database COUNT instead

---

## Phase 6: Testing

### 6.1 Run Existing Tests
```bash
# Frontend tests
cd auralis-web/frontend
npm run test:memory

# Specific test files affected:
# - components/library/__tests__/CozyAlbumGrid.test.tsx
# - components/library/__tests__/CozyArtistList.test.tsx
# - hooks/library/__tests__/useLibraryQuery.test.ts
# - hooks/shared/__tests__/useInfiniteScroll.test.ts
```

**Expected**: All tests pass without modification (API contracts unchanged)

### 6.2 Verify Infinite Scroll Behavior
**Manual Testing Checklist**:
- [ ] Albums: Scroll to bottom → Load more items
- [ ] Albums: Check total count accuracy
- [ ] Artists: Scroll to bottom → Load more items
- [ ] Artists: Check alphabetical grouping still works
- [ ] Artists: Check context menu still works
- [ ] Search: Test search in albums, artists, tracks
- [ ] Error handling: Verify error states display correctly

### 6.3 Performance Verification
**Metrics to Check**:
- [ ] Artist search latency: Should drop from ~200ms to ~50ms (N+1 fix)
- [ ] Album pagination: Should be same or faster (IntersectionObserver vs scroll events)
- [ ] Artist pagination: Should be same or faster (IntersectionObserver vs scroll events)

---

## Phase 7: Cleanup & Documentation

### 7.1 Update Component Documentation
**Files to Update**:
- `CozyAlbumGrid.tsx` - Update docstring to reference new hooks
- `CozyArtistList.tsx` - Update docstring to reference new hooks

### 7.2 Verify Import Paths
All components should use absolute paths:
```typescript
// ✅ Correct
import { useAlbumsQuery } from '@/hooks/library';
import { useInfiniteScroll } from '@/hooks/shared';

// ❌ Wrong
import { useAlbumsQuery } from '../../../hooks/library';
```

### 7.3 Update CLAUDE.md
Update the project documentation to reflect the consolidated pattern:
- Reference `useLibraryQuery` as the single canonical pagination pattern
- Update examples to show all three data types (tracks, albums, artists)
- Document the new `useGroupedArtists` hook for domain-specific grouping

---

## Summary of Changes

| Phase | Changes | Files | LOC Impact |
|-------|---------|-------|-----------|
| **1** | Fix artist search N+1 | `routers/artists.py` | -2 duplicate queries |
| **2** | Album consolidation | CozyAlbumGrid, useAlbumGrid* | -99 lines |
| **3** | Artist consolidation | CozyArtistList, useArtistListPagination | -150 lines |
| **4** | Remove duplicate hook | useInfiniteScroll (Views) | -50 lines |
| **5** | Verify endpoints | N/A (verification only) | TBD |
| **6** | Testing | Run tests | 0 lines |
| **7** | Documentation | CLAUDE.md, docstrings | Documentation only |
| **Total** | | 7 files modified, 3 deleted | -300+ lines |

---

## Risk Assessment

### Low Risk
- ✅ Using proven patterns (Tracks view already works perfectly)
- ✅ Hook API is compatible (useLibraryQuery supports albums/artists)
- ✅ Shared useInfiniteScroll is well-tested (540+ test cases)
- ✅ No database schema changes needed

### Medium Risk
- ⚠️ Backend search fix requires understanding repository layer
- ⚠️ Need to verify all endpoints use same response structure
- ⚠️ Artist grouping logic moved to new hook (need to test)

### Mitigation
- Start with album consolidation (simpler, fewer concerns)
- Test each phase before moving to next
- Backend fix is isolated to one file
- New `useGroupedArtists` hook is simple and well-scoped

---

## Implementation Order
1. **Phase 1**: Backend artist search fix (enables performance improvement)
2. **Phase 2**: Album consolidation (simpler, fewer side effects)
3. **Phase 3**: Artist consolidation (more complex due to grouping)
4. **Phase 4**: Remove duplicate scroll hook
5. **Phase 5**: Verify pattern consistency
6. **Phase 6**: Testing
7. **Phase 7**: Documentation update

---

## Success Criteria
- ✅ All three views use `useLibraryQuery` + shared `useInfiniteScroll`
- ✅ No duplicate scroll detection logic in codebase
- ✅ Artist search latency improves by ~75% (backend fix)
- ✅ All existing tests pass without modification
- ✅ Manual testing confirms infinite scroll works for all views
- ✅ ~300 lines of duplicate code eliminated
- ✅ Architecture follows DRY principle from CLAUDE.md
