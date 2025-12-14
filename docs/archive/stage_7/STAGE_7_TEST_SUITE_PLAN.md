# Stage 7 Test Suite Extension Plan

## Overview
This document outlines a comprehensive testing strategy for Stage 7 refactoring (TrackRow, SimilarTracks, CozyLibraryView component decomposition). The refactoring extracted 13 custom hooks and 12+ UI subcomponents that require comprehensive test coverage.

---

## Current Test Status

### Existing Tests
- **Total frontend tests**: 70 files
- **Library component tests**: ~10 files (TrackRow.test.tsx exists but needs update)
- **Discovery component tests**: 0 files
- **Hook tests**: Minimal coverage

### New Artifacts from Stage 7 Refactoring
- **13 Custom Hooks**: Need test files (13 files)
- **12+ UI Subcomponents**: Need test files (12 files)
- **3 Parent Components (refactored)**: Need updated tests (3 files)

**Total test files needed: ~28 files**

---

## Phase 1: Custom Hook Tests (Highest Priority)

### Priority 1A: TrackRow Hooks (4 tests)

#### 1. `useTrackRowHandlers.test.ts`
**Location**: `src/components/library/Items/__tests__/useTrackRowHandlers.test.ts`

**Dependencies to Mock**:
- No external dependencies
- Pure logic handlers

**Test Cases**:
```
✓ Should initialize with default handler functions
✓ handlePlayClick - should call onPlay when track not currently playing
✓ handlePlayClick - should call onPause when track is currently playing
✓ handlePlayClick - should prevent default event propagation
✓ handleRowClick - should call onPlay with track ID
✓ handleRowDoubleClick - should call onDoubleClick callback
✓ handleRowDoubleClick - should handle undefined onDoubleClick gracefully
✓ useCallback dependency arrays - should memoize handlers correctly
✓ Handler stability - should maintain referential equality across renders
```

**Test Type**: Unit (hook logic)
**Estimated Lines**: 80-100
**Complexity**: Low

---

#### 2. `useTrackContextMenu.test.ts`
**Location**: `src/components/library/Items/__tests__/useTrackContextMenu.test.ts`

**Dependencies to Mock**:
- `useToast` hook (success, error, info methods)
- `playlistService.getPlaylists()` - API call
- `playlistService.addTracksToPlaylist()` - API call

**Test Cases**:
```
✓ Should initialize with null context menu position
✓ handleMoreClick - should set context menu position
✓ handleTrackContextMenu - should prevent default and set position
✓ handleCloseContextMenu - should reset context menu position
✓ Playlist loading - should fetch playlists on demand
✓ Playlist loading - should handle fetch errors gracefully
✓ handleAddToPlaylist - should add track to playlist and show toast
✓ handleAddToPlaylist - should handle API errors
✓ handleCreatePlaylist - should create and add to new playlist
✓ contextMenuActions - should generate correct action callbacks
✓ contextMenuActions - should handle all optional callbacks
✓ State isolation - position state should not leak between instances
```

**Test Type**: Unit + Integration (hook + external deps)
**Estimated Lines**: 150-180
**Complexity**: Medium

---

#### 3. `useTrackImage.test.ts`
**Location**: `src/components/library/Items/__tests__/useTrackImage.test.ts`

**Dependencies to Mock**:
- None (pure state management)

**Test Cases**:
```
✓ Should initialize with imageError false
✓ handleImageError - should set imageError to true
✓ shouldShowImage - should return true when albumArt provided and no error
✓ shouldShowImage - should return false when imageError is true
✓ shouldShowImage - should return false when albumArt is undefined
✓ Handler stability - handleImageError should maintain referential equality
✓ Multiple image loads - should handle sequential image errors
```

**Test Type**: Unit (state management)
**Estimated Lines**: 70-80
**Complexity**: Low

---

#### 4. `useTrackFormatting.test.ts`
**Location**: `src/components/library/Items/__tests__/useTrackFormatting.test.ts`

**Dependencies to Mock**:
- None (pure utility)

**Test Cases**:
```
✓ Should expose formatDuration utility
✓ formatDuration - should format 0 seconds as "0:00"
✓ formatDuration - should format 60 seconds as "1:00"
✓ formatDuration - should format 3661 seconds as "61:01"
✓ formatDuration - should pad single-digit seconds
✓ formatDuration - should handle large durations (hours)
✓ Handler stability - formatDuration should maintain referential equality
✓ Edge cases - should handle negative durations gracefully
```

**Test Type**: Unit (utility)
**Estimated Lines**: 70-90
**Complexity**: Low

---

### Priority 1B: SimilarTracks Hooks (2 tests)

#### 5. `useSimilarTracksLoader.test.ts`
**Location**: `src/components/features/discovery/__tests__/useSimilarTracksLoader.test.ts`

**Dependencies to Mock**:
- `similarityService.findSimilar()` - API call
- Returns `SimilarTrack[]`

**Test Cases**:
```
✓ Should initialize with empty tracks and false loading
✓ Should fetch similar tracks when trackId changes
✓ Should set loading state during fetch
✓ Should handle successful track loading
✓ Should handle API errors gracefully
✓ Should reset tracks on error
✓ Should respect limit parameter
✓ Should use graph mode when specified
✓ Should skip fetch when trackId is null
✓ Should clear tracks when trackId becomes null
✓ Should re-fetch when limit or useGraph changes
✓ useEffect dependency array - should trigger on trackId, limit, useGraph changes
✓ useCallback - loadSimilarTracks should be memoized
```

**Test Type**: Integration (async hook + mocked API)
**Estimated Lines**: 140-160
**Complexity**: Medium-High

---

#### 6. `useSimilarTracksFormatting.test.ts`
**Location**: `src/components/features/discovery/__tests__/useSimilarTracksFormatting.test.ts`

**Dependencies to Mock**:
- `tokens.colors` - design system tokens

**Test Cases**:
```
✓ Should expose getSimilarityColor and formatDuration utilities
✓ getSimilarityColor - should return success color for 90%+ similarity
✓ getSimilarityColor - should return purple color for 80-89% similarity
✓ getSimilarityColor - should return secondary color for 70-79% similarity
✓ getSimilarityColor - should return gray color for <70% similarity
✓ getSimilarityColor - should handle boundary values (0.90, 0.80, 0.70)
✓ formatDuration - should format duration correctly
✓ formatDuration - should return empty string for undefined
✓ Handler stability - both utilities should maintain referential equality
```

**Test Type**: Unit (utility)
**Estimated Lines**: 100-120
**Complexity**: Low-Medium

---

### Priority 1C: CozyLibraryView Hooks (4 tests)

#### 7. `usePlaybackState.test.ts`
**Location**: `src/components/library/__tests__/usePlaybackState.test.ts`

**Dependencies to Mock**:
- `usePlayerAPI()` hook - playTrack method
- `useToast()` hook - success method
- Track object type

**Test Cases**:
```
✓ Should initialize with undefined currentTrackId and false isPlaying
✓ handlePlayTrack - should call playTrack and update state
✓ handlePlayTrack - should show success toast with track title
✓ handlePlayTrack - should call optional onTrackPlay callback
✓ handlePlayTrack - should handle async playTrack errors
✓ handlePause - should set isPlaying to false
✓ State isolation - should not share state between hook instances
✓ useCallback - handlers should maintain referential equality
✓ Async handling - should properly await playTrack promise
```

**Test Type**: Integration (hook composition)
**Estimated Lines**: 120-140
**Complexity**: Medium

---

#### 8. `useNavigationState.test.ts`
**Location**: `src/components/library/__tests__/useNavigationState.test.ts`

**Dependencies to Mock**:
- None (pure state)

**Test Cases**:
```
✓ Should initialize with null selection states
✓ Should reset all states when view prop changes
✓ handleBackFromAlbum - should clear selectedAlbumId
✓ handleBackFromAlbum - should preserve selectedArtistId
✓ handleBackFromArtist - should clear both artist states
✓ handleAlbumClick - should set selectedAlbumId
✓ handleArtistClick - should set selectedArtistId and selectedArtistName
✓ State transitions - album click then artist click works correctly
✓ Reset on view change - should clear all when view prop updates
✓ useCallback - all handlers should be memoized
```

**Test Type**: Unit (state management)
**Estimated Lines**: 120-140
**Complexity**: Low-Medium

---

#### 9. `useMetadataEditing.test.ts`
**Location**: `src/components/library/__tests__/useMetadataEditing.test.ts`

**Dependencies to Mock**:
- `useToast()` hook - success method
- onFetchTracks callback

**Test Cases**:
```
✓ Should initialize with dialog closed and null trackId
✓ handleEditMetadata - should set trackId and open dialog
✓ handleCloseEditDialog - should close dialog and reset trackId
✓ handleSaveMetadata - should call onFetchTracks
✓ handleSaveMetadata - should show success toast
✓ Dialog state - open should be true after handleEditMetadata
✓ Dialog state - open should be false after handleCloseEditDialog
✓ useCallback - all handlers should be memoized
✓ Props passed to EditMetadataDialog - should receive correct values
```

**Test Type**: Unit (state management)
**Estimated Lines**: 100-120
**Complexity**: Low

---

#### 10. `useBatchOperations.test.ts`
**Location**: `src/components/library/__tests__/useBatchOperations.test.ts`

**Dependencies to Mock**:
- `useToast()` hook (success, error, info)
- `fetch()` API for queue and favorite operations
- `confirm()` for deletion confirmation

**Test Cases**:
```
✓ Should expose all four batch operation handlers
✓ handleBulkAddToQueue - should add all selected tracks to queue
✓ handleBulkAddToQueue - should show success toast
✓ handleBulkAddToQueue - should clear selection after adding
✓ handleBulkAddToQueue - should handle API errors
✓ handleBulkAddToPlaylist - should show "coming soon" info
✓ handleBulkRemove - should prompt for confirmation
✓ handleBulkRemove (favorites) - should delete from favorites
✓ handleBulkRemove (library) - should show implementation needed message
✓ handleBulkRemove - should call onFetchTracks after success
✓ handleBulkToggleFavorite - should toggle favorite for all tracks
✓ handleBulkToggleFavorite - should call onFetchTracks after success
✓ Error handling - should show error toast on API failure
✓ Selection clearing - should clear selection after operations
✓ View-specific behavior - should behave differently for favorites vs library
```

**Test Type**: Integration (async operations + mocks)
**Estimated Lines**: 180-220
**Complexity**: High

---

## Phase 2: UI Subcomponent Tests (Medium Priority)

### Priority 2A: TrackRow Subcomponents (3 tests)

#### 11. `TrackRowPlayButton.test.tsx`
**Location**: `src/components/library/Items/__tests__/TrackRowPlayButton.test.tsx`

**Test Cases**:
```
✓ Should render play icon when not currently playing
✓ Should render pause icon when currently playing and is current track
✓ Should call onClick handler when clicked
✓ Should not show pause icon if isCurrent is false
✓ Should have correct aria-label for accessibility
✓ Should have correct size prop passed to MUI IconButton
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 80-100
**Complexity**: Low

---

#### 12. `TrackRowAlbumArt.test.tsx`
**Location**: `src/components/library/Items/__tests__/TrackRowAlbumArt.test.tsx`

**Test Cases**:
```
✓ Should render image when albumArt provided and shouldShowImage true
✓ Should render MusicNote icon when no album art
✓ Should call onImageError when image fails to load
✓ Should pass correct alt text to image
✓ Should render fallback icon when shouldShowImage is false
✓ Should handle missing album name gracefully
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 100-120
**Complexity**: Low-Medium

---

#### 13. `TrackRowMetadata.test.tsx`
**Location**: `src/components/library/Items/__tests__/TrackRowMetadata.test.tsx`

**Test Cases**:
```
✓ Should render track title
✓ Should render artist name
✓ Should render album name when provided
✓ Should render formatted duration
✓ Should apply correct styling when isCurrent is true
✓ Should apply different styling when isCurrent is false
✓ Should hide album on mobile (display: none)
✓ Should show all metadata fields
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 100-120
**Complexity**: Low

---

### Priority 2B: SimilarTracks Subcomponents (6 tests)

#### 14. `SimilarTracksLoadingState.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksLoadingState.test.tsx`

**Test Cases**:
```
✓ Should render circular progress spinner
✓ Should render loading text "Finding similar tracks..."
✓ Should have correct color from design tokens
✓ Should have correct spinner size
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 60-80
**Complexity**: Low

---

#### 15. `SimilarTracksErrorState.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksErrorState.test.tsx`

**Test Cases**:
```
✓ Should render error message from props
✓ Should render Alert component with error severity
✓ Should display custom error text correctly
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 60-80
**Complexity**: Low

---

#### 16. `SimilarTracksEmptyState.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksEmptyState.test.tsx`

**Test Cases**:
```
✓ Should render "play a track" message when trackId is null
✓ Should render "no similar tracks" message when trackId provided but no results
✓ Should render MusicNote icon when trackId is null
✓ Should render Sparkles icon when trackId provided
✓ Should conditionally render secondary message based on trackId
```

**Test Type**: Component (UI rendering + conditional)
**Estimated Lines**: 100-120
**Complexity**: Low-Medium

---

#### 17. `SimilarTracksListItem.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksListItem.test.tsx`

**Test Cases**:
```
✓ Should render track title
✓ Should render artist name
✓ Should render duration when provided
✓ Should render similarity score percentage
✓ Should call onClick with track when clicked
✓ Should show divider when not last item
✓ Should not show divider when last item (totalCount check)
✓ Should apply correct similarity color based on score
✓ Should have tooltip showing full percentage
```

**Test Type**: Component (UI rendering + interaction)
**Estimated Lines**: 120-150
**Complexity**: Medium

---

#### 18. `SimilarTracksHeader.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksHeader.test.tsx`

**Test Cases**:
```
✓ Should render "Similar Tracks" title
✓ Should render description text
✓ Should render Sparkles icon
✓ Should have correct border styling
✓ Should have correct spacing and layout
```

**Test Type**: Component (UI rendering)
**Estimated Lines**: 70-90
**Complexity**: Low

---

#### 19. `SimilarTracksFooter.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksFooter.test.tsx`

**Test Cases**:
```
✓ Should show "⚡ Fast lookup" when useGraph is true
✓ Should show "🔍 Real-time search" when useGraph is false
✓ Should display track count
✓ Should have correct border styling
✓ Should have correct spacing
```

**Test Type**: Component (UI rendering + conditional)
**Estimated Lines**: 80-100
**Complexity**: Low

---

#### 20. `SimilarTracksList.test.tsx`
**Location**: `src/components/features/discovery/__tests__/SimilarTracksList.test.tsx`

**Test Cases**:
```
✓ Should render header component
✓ Should render footer component
✓ Should render all track items
✓ Should call onTrackSelect when track clicked
✓ Should pass correct props to list items
✓ Should pass formatting utilities to items
✓ Should handle empty tracks array
```

**Test Type**: Component (composition + integration)
**Estimated Lines**: 120-150
**Complexity**: Medium

---

## Phase 3: Updated Parent Component Tests (Lower Priority)

### Priority 3A: Refactored Component Tests (3 tests)

#### 21. `TrackRow.test.tsx` (UPDATE)
**Location**: `src/components/library/__tests__/TrackRow.test.tsx`

**Changes Needed**:
- Update imports to mock new hooks
- Update test setup to work with extracted subcomponents
- Add tests for new hook integrations
- Verify backward compatibility

**New Test Cases**:
```
✓ Should still render complete track row
✓ Should still handle play/pause correctly
✓ Should still show context menu
✓ Should render TrackRowPlayButton subcomponent
✓ Should render TrackRowAlbumArt subcomponent
✓ Should render TrackRowMetadata subcomponent
✓ Should pass correct props to all subcomponents
✓ Integration - complete track row behavior preserved
```

**Test Type**: Component + Integration (refactored)
**Estimated Lines**: 150-180 (existing test + new cases)
**Complexity**: Medium

---

#### 22. `SimilarTracks.test.tsx` (NEW)
**Location**: `src/components/features/discovery/__tests__/SimilarTracks.test.tsx`

**Test Cases**:
```
✓ Should render loading state initially
✓ Should render similar tracks list when data loaded
✓ Should render error state when fetch fails
✓ Should render empty state when no trackId
✓ Should call onTrackSelect when track clicked
✓ Should respect limit prop
✓ Should respect useGraph prop
✓ Should refetch when trackId changes
✓ Integration - complete component behavior
```

**Test Type**: Component + Integration (refactored)
**Estimated Lines**: 160-200
**Complexity**: Medium-High

---

#### 23. `CozyLibraryView.test.tsx` (UPDATE)
**Location**: `src/components/library/__tests__/CozyLibraryView.test.tsx`

**Changes Needed**:
- Update imports to mock new hooks
- Add tests for new hook integrations
- Verify batch operations work
- Verify navigation state works
- Verify playback state works
- Verify metadata editing works

**New Test Cases**:
```
✓ Should still render main library view
✓ Should still handle track selection
✓ Should still handle search/filter
✓ Should use usePlaybackState hook
✓ Should use useNavigationState hook
✓ Should use useMetadataEditing hook
✓ Should use useBatchOperations hook
✓ Batch operations - should handle bulk queue add
✓ Batch operations - should handle favorites toggle
✓ Navigation - should switch to album view
✓ Navigation - should switch to artist view
✓ Playback - should play tracks correctly
✓ Metadata - should open edit dialog
✓ Integration - complete component behavior preserved
```

**Test Type**: Component + Integration (refactored)
**Estimated Lines**: 250-300 (comprehensive)
**Complexity**: High

---

## Phase 4: Integration & E2E Tests (Lowest Priority)

#### 24. TrackRow Integration Test
**Test**: Full track row interaction flow
- Play button → playback hooks → context menu → playlist operations

---

#### 25. SimilarTracks Integration Test
**Test**: Full similar tracks flow
- Load similar tracks → click track → playback

---

#### 26. CozyLibraryView Integration Test
**Test**: Full library flow
- Search → select → batch operations → playback

---

## Implementation Roadmap

### Session 1: Phase 1A (TrackRow Hooks)
- Create 4 hook test files
- Set up mocking patterns
- Estimate: 2-3 hours

### Session 2: Phase 1B + 1C (Remaining Hooks)
- Create 6 remaining hook test files
- Complete hook coverage
- Estimate: 3-4 hours

### Session 3: Phase 2 (UI Subcomponents)
- Create 10 subcomponent test files
- Set up component rendering tests
- Estimate: 3-4 hours

### Session 4: Phase 3 (Updated Parent Components)
- Update 3 existing component tests
- Add integration test cases
- Estimate: 3-4 hours

### Session 5: Phase 4 (Integration Tests)
- Create end-to-end flow tests
- Final validation
- Estimate: 2-3 hours

**Total Estimated Effort**: 13-18 hours across 5 sessions

---

## Testing Infrastructure Requirements

### Mocking Patterns
```typescript
// Example: Hook mocking
vi.mock('../../hooks/usePlayerAPI', () => ({
  usePlayerAPI: vi.fn(() => ({
    playTrack: vi.fn().mockResolvedValue(undefined),
  })),
}));

// Example: API mocking
vi.mock('../services/similarityService', () => ({
  findSimilar: vi.fn().mockResolvedValue([
    { track_id: 1, title: 'Similar Track', similarity_score: 0.95 },
  ]),
}));

// Example: Design tokens
vi.mock('@/design-system/tokens', () => ({
  tokens: {
    colors: {
      accent: { success: '#00AA00', purple: '#7C3AED' },
      text: { primary: '#FFF', secondary: '#999' },
    },
  },
}));
```

### Test Utilities Available
- `render()` from `@/test/test-utils` (includes all providers)
- `screen`, `fireEvent`, `waitFor` from testing library
- `userEvent` for user interactions
- `vi` for Vitest mocking/spying

### File Structure
```
src/components/library/Items/__tests__/
├── TrackRow.test.tsx (UPDATE)
├── TrackRowPlayButton.test.tsx (NEW)
├── TrackRowAlbumArt.test.tsx (NEW)
├── TrackRowMetadata.test.tsx (NEW)
├── useTrackRowHandlers.test.ts (NEW)
├── useTrackContextMenu.test.ts (NEW)
├── useTrackImage.test.ts (NEW)
└── useTrackFormatting.test.ts (NEW)

src/components/features/discovery/__tests__/
├── SimilarTracks.test.tsx (NEW)
├── SimilarTracksLoadingState.test.tsx (NEW)
├── SimilarTracksErrorState.test.tsx (NEW)
├── SimilarTracksEmptyState.test.tsx (NEW)
├── SimilarTracksHeader.test.tsx (NEW)
├── SimilarTracksListItem.test.tsx (NEW)
├── SimilarTracksFooter.test.tsx (NEW)
├── SimilarTracksList.test.tsx (NEW)
├── useSimilarTracksLoader.test.ts (NEW)
└── useSimilarTracksFormatting.test.ts (NEW)

src/components/library/__tests__/
├── CozyLibraryView.test.tsx (UPDATE)
├── usePlaybackState.test.ts (NEW)
├── useNavigationState.test.ts (NEW)
├── useMetadataEditing.test.ts (NEW)
└── useBatchOperations.test.ts (NEW)
```

---

## Success Criteria

✅ **Coverage Goals**:
- All 13 hooks: 90%+ coverage
- All 12+ subcomponents: 85%+ coverage
- 3 parent components: 80%+ coverage
- Overall Stage 7: 85%+ coverage increase

✅ **Quality Metrics**:
- All tests passing
- No console errors in tests
- Mocks properly isolated
- No test interdependencies
- Clear test names and documentation

✅ **Maintenance**:
- Easy to update when components change
- Clear mock setup patterns
- Reusable test utilities
- Well-documented test cases

---

## Notes

### Dependencies & Order
- **Must test Phase 1A before 1B** (hooks used in parent component tests)
- **Can test Phase 2 in parallel** (independent subcomponent tests)
- **Phase 3 depends on Phase 1** (parent component tests use hook mocks)
- **Phase 4 depends on Phases 1-3** (integration tests use all components)

### Common Pitfalls to Avoid
1. ❌ Not mocking hooks properly before testing parent components
2. ❌ Testing implementation details instead of behavior
3. ❌ Not cleaning up mocks between tests
4. ❌ Using hardcoded values instead of design tokens in tests
5. ❌ Forgetting to test error states and edge cases
6. ❌ Not testing props passing to subcomponents

### Recommended Testing Order Within Session
1. Start with **simple utility hooks** (useTrackFormatting, useSimilarTracksFormatting)
2. Then **state management hooks** (useNavigationState, useMetadataEditing)
3. Then **complex hooks** (useBatchOperations, useSimilarTracksLoader)
4. Then **simple UI components** (loading states, footers)
5. Then **complex UI components** (list item, list orchestrator)
6. Finally **parent component integration tests**

---

## References

### Documentation
- Testing Guidelines: `docs/guides/FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md`
- Test Utils: `src/test/test-utils.tsx`
- Mock Handlers: `src/test/mocks/handlers.ts`

### Example Test Pattern
See `src/components/library/__tests__/TrackRow.test.tsx` for current testing patterns

### Design System
- Tokens: `src/design-system/tokens.ts`
- Colors: `src/components/library/Color.styles.ts`

---

## Sign-Off

**Created**: November 23, 2025
**Status**: Ready for Phase 1 implementation
**Next Steps**: Begin Phase 1A (TrackRow hooks) in next session
