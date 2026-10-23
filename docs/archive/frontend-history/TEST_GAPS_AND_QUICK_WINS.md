# Frontend Test Suite - Gaps & Quick Wins

## Overview
This document identifies specific testing gaps and quick-win improvements for the Auralis frontend test suite.

Current State: 35 test files, 16,621 LOC, 750+ test cases, ~45% coverage
Target: 70%+ coverage with focused component testing

---

## 1. Critical Components Needing Tests (Impact Priority)

### TIER 1: Core User Experience (MUST TEST FIRST)

These 6 components affect the primary user journey. Tests needed in Week 1.

#### 1. BottomPlayerBarUnified.tsx
- **Location**: `/src/components/BottomPlayerBarUnified.tsx`
- **Impact**: Main player interface - users interact constantly
- **Lines**: ~300 (estimate for tests)
- **Test Areas**:
  - Play/pause button rendering and click handler
  - Track info display (title, artist, album art)
  - Progress bar interactions (seeking)
  - Volume control slider
  - Queue navigation (previous/next)
  - Time display (current/duration)
  - Enhancement indicator visibility
  - WebSocket state synchronization

**Dependencies**: WebSocketContext, usePlayerAPI hook

**Sample Test Structure**:
```tsx
describe('BottomPlayerBarUnified', () => {
  it('renders play/pause button', () => { /* ... */ })
  it('displays current track info', () => { /* ... */ })
  it('updates on WebSocket player state change', () => { /* ... */ })
  it('calls player API on pause', () => { /* ... */ })
  it('displays progress with seeking', () => { /* ... */ })
  // ... 15-20 more tests
})
```

#### 2. CozyLibraryView.tsx
- **Location**: `/src/components/CozyLibraryView.tsx`
- **Impact**: Primary library browsing interface
- **Lines**: ~500 (estimate for tests)
- **Test Areas**:
  - Album grid rendering
  - Album card click to detail view
  - Artist list rendering
  - Track list display
  - Search filter integration
  - Virtual scrolling for large libraries
  - Empty state display
  - Loading state display
  - Error state handling

**Dependencies**: CozyAlbumGrid, CozyArtistList, TrackListView, GlobalSearch

**Note**: May need to break into sub-component tests

#### 3. EnhancementPaneV2.tsx
- **Location**: `/src/components/enhancement-pane-v2/EnhancementPaneV2.tsx`
- **Impact**: Audio processing control interface
- **Lines**: ~400 (estimate for tests)
- **Test Areas**:
  - Preset selector rendering and selection
  - Parameter display and adjustment
  - Real-time audio feedback
  - Saving/loading presets
  - Enhancement toggle enable/disable
  - Audio characteristics display
  - Parameter limit validation

**Dependencies**: EnhancementProvider, EnhancementContext, AudioCharacteristics

#### 4. TrackRow.tsx
- **Location**: `/src/components/library/TrackRow.tsx`
- **Impact**: Track display in lists - frequently rendered
- **Lines**: ~250 (estimate for tests)
- **Test Areas**:
  - Track info display (title, artist, duration)
  - Artwork thumbnail
  - Selection checkbox
  - Context menu trigger
  - Double-click to play
  - Drag handle rendering
  - Hover states

**Dependencies**: useTrackSelection, TrackContextMenu

#### 5. PlayerBarV2.tsx
- **Location**: `/src/components/player-bar-v2/PlayerBarV2.tsx`
- **Impact**: New player bar component
- **Lines**: ~300 (estimate for tests)
- **Test Areas**:
  - All player bar controls
  - Volume control
  - Enhancement toggle
  - Track progress bar
  - State synchronization

**Dependencies**: PlaybackControls, VolumeControl, ProgressBar, TrackInfo

#### 6. TrackCard.tsx
- **Location**: `/src/components/track/TrackCard.tsx`
- **Impact**: Card-based track display
- **Lines**: ~200 (estimate for tests)
- **Test Areas**:
  - Album artwork display
  - Track metadata display
  - Play button on hover
  - Selection state
  - Context menu access

**Dependencies**: Artwork service, useTrackSelection

---

### TIER 2: Supporting Components (Priority: HIGH)

Test these after Tier 1, Week 2-3.

#### Library View Components (13 files, ~1,500 LOC total)

1. **AlbumDetailView.tsx** (250 LOC)
   - Album metadata display
   - Track list within album
   - Album art display
   - Navigation back to library

2. **ArtistDetailView.tsx** (250 LOC)
   - Artist metadata
   - Album list for artist
   - All tracks by artist

3. **TrackListView.tsx** (250 LOC)
   - Full track table view
   - Sorting capabilities
   - Selection for batch operations
   - Context menu per track

4. **DraggableTrackRow.tsx** (150 LOC)
   - Drag handle rendering
   - Drag operation handling
   - Drop zone integration

5. **SelectableTrackRow.tsx** (150 LOC)
   - Selection checkbox
   - Multi-select handling
   - Highlight on selection

6. **BatchActionsToolbar.tsx** (150 LOC)
   - Bulk action buttons
   - Delete confirmation
   - Playlist addition

7. **LibraryHeader.tsx** (100 LOC)
   - View toggle buttons
   - Search input
   - Filter options

8. **GlobalSearch.tsx** (150 LOC)
   - Search input
   - Results display
   - Filter options

9. **LibraryEmptyState.tsx** (100 LOC)
   - Empty library display
   - Action prompts

10. **CozyAlbumGrid.tsx** (100 LOC)
    - Album grid layout
    - Album card display

11. **CozyArtistList.tsx** (100 LOC)
    - Artist list rendering
    - Artist card display

12. **EditMetadataDialog.tsx** (200 LOC)
    - Form inputs
    - Save/cancel actions
    - Validation

13. **LibraryViewRouter.tsx** (100 LOC)
    - Router state management
    - View switching

#### Enhancement Pane Sub-components (8 files, ~1,000 LOC total)

1. **AudioCharacteristics.tsx** (150 LOC)
   - Frequency response display
   - Dynamic range display
   - Loudness display

2. **ParameterBar.tsx** (150 LOC)
   - Parameter slider display
   - Min/max value display
   - Real-time value changes

3. **ParameterChip.tsx** (100 LOC)
   - Parameter tag display
   - Value formatting

4. **ProcessingParameters.tsx** (150 LOC)
   - Multiple parameter display
   - Grid/list toggle

5. **InfoBox.tsx** (100 LOC)
   - Help text display
   - Tooltip functionality

6. **LoadingState.tsx** (80 LOC)
   - Loading spinner
   - Progress text

7. **EmptyState.tsx** (80 LOC)
   - Empty pane display
   - Action prompts

8. **EnhancementToggle.tsx** (100 LOC)
   - Toggle switch
   - Enable/disable state

#### Player Components (8 files, ~800 LOC total)

1. **PlaybackControls.tsx** (150 LOC)
   - Play/pause/skip buttons
   - Button click handlers

2. **ProgressBar.tsx** (150 LOC)
   - Progress display
   - Seeking interaction
   - Duration display

3. **TrackInfo.tsx** (120 LOC)
   - Track metadata display
   - Album art
   - Artist/album links

4. **VolumeControl.tsx** (120 LOC)
   - Volume slider
   - Mute button

5. **PlayerControls.tsx** (100 LOC)
   - Control layout
   - Button arrangement

6. **PlayerBarV2Connected.tsx** (100 LOC)
   - WebSocket integration
   - State synchronization

7. **TrackQueue.tsx** (120 LOC)
   - Queue list display
   - Queue item drag/drop

8. **EnhancementToggle.tsx** (100 LOC)
   - Toggle button
   - State persistence

---

## 2. Missing Service Tests (Priority: HIGH)

These services handle critical business logic.

### processingService.ts (CRITICAL)
- **Impact**: Audio processing requests
- **Test Coverage**: 0%
- **Estimated Effort**: 3-4 hours
- **Estimated LOC**: 300-400

**What to Test**:
- Processing request submission
- Preset application
- Parameter adjustment
- Progress tracking
- Error handling

### mseStreamingService.ts (HIGH)
- **Impact**: Media streaming
- **Test Coverage**: 0%
- **Estimated Effort**: 2-3 hours
- **Estimated LOC**: 250-300

**What to Test**:
- MSE buffer management
- Chunk appending
- Format codec handling
- Error recovery

### RealTimeAnalysisStream.ts (MEDIUM)
- **Impact**: Real-time audio analysis
- **Test Coverage**: 0%
- **Estimated Effort**: 2 hours
- **Estimated LOC**: 200-250

**What to Test**:
- Stream initialization
- Data frame processing
- Real-time updates
- Connection lifecycle

### keyboardShortcutsService.ts (MEDIUM)
- **Impact**: Keyboard handling
- **Test Coverage**: 0%
- **Estimated Effort**: 1.5 hours
- **Estimated LOC**: 150-200

**What to Test**:
- Shortcut registration
- Key binding validation
- Command execution
- Conflict detection

### AnalysisExportService.ts (LOW)
- **Impact**: Export functionality
- **Test Coverage**: 0%
- **Estimated Effort**: 1.5 hours
- **Estimated LOC**: 150-200

**What to Test**:
- Export format options
- File generation
- Data formatting

---

## 3. Missing Hook Tests (Priority: MEDIUM)

These hooks manage state and side effects.

### useUnifiedWebMAudioPlayer.ts (CRITICAL)
- **Current**: 0%
- **Impact**: Audio playback engine
- **Effort**: 250-300 LOC, 2-3 hours
- **Key Tests**:
  - Play/pause/stop functionality
  - Volume control
  - Progress tracking
  - Format codec support

### useWebSocket.ts (HIGH)
- **Current**: 0%
- **Impact**: Real-time updates
- **Effort**: 200-250 LOC, 2 hours
- **Key Tests**:
  - Connection establishment
  - Message handling
  - Reconnection logic
  - Error recovery

### useDragAndDrop.ts (MEDIUM)
- **Current**: 0%
- **Impact**: Drag-and-drop state
- **Effort**: 150-200 LOC, 1.5 hours
- **Key Tests**:
  - Drag state tracking
  - Drop zone validation
  - Item reordering

### useLibraryData.ts (MEDIUM)
- **Current**: 0%
- **Impact**: Data fetching
- **Effort**: 150-200 LOC, 1.5 hours
- **Key Tests**:
  - Data fetching
  - Caching behavior
  - Error handling
  - Pagination

### useTrackSelection.ts (MEDIUM)
- **Current**: 0%
- **Impact**: Multi-select state
- **Effort**: 150-200 LOC, 1.5 hours
- **Key Tests**:
  - Selection toggling
  - Select all/none
  - Range selection

### Others with Tests (31% coverage)
- useInfiniteScroll ✓ (534 LOC)
- useKeyboardShortcuts ✓ (599 LOC)
- usePlayerAPI ✓ (233 LOC)

---

## 4. Quick Wins - Easy Tests with High Impact

These are easy to implement and provide immediate value.

### Navigation Components (Effort: LOW, Impact: MEDIUM)

#### SearchBar.tsx (150 LOC test)
- Input field rendering
- Search query input
- Enter key submission
- Clear button functionality
- Placeholder text

#### ViewToggle.tsx (100 LOC test)
- Button group rendering
- View mode selection
- Icon display
- Active state styling

#### GlobalSearch.tsx (150 LOC test)
- Search modal opening
- Search input handling
- Results display
- Close functionality

### Dialog/Modal Components (Effort: LOW-MEDIUM, Impact: MEDIUM)

#### SettingsDialog.tsx (200 LOC test)
- Dialog opening/closing
- Settings form rendering
- Save functionality
- Cancel functionality
- Validation messages

#### CreatePlaylistDialog.tsx (150 LOC test)
- Dialog rendering
- Form submission
- Validation
- Error handling

#### EditPlaylistDialog.tsx (150 LOC test)
- Playlist data loading
- Form population
- Edit submission
- Delete functionality

### Shared/Utility Components (Effort: LOW, Impact: LOW-MEDIUM)

#### Toast.tsx (100 LOC test)
- Toast rendering
- Auto-dismiss
- Different types (success, error, info)
- Close button

#### LoadingSpinner.tsx (80 LOC test)
- Spinner rendering
- Loading text
- Size variants

#### ProgressiveImage.tsx (120 LOC test)
- Image loading
- Placeholder display
- Fallback handling

#### EmptyState.tsx (100 LOC test)
- Icon display
- Text content
- Action button

#### DropZone.tsx (150 LOC test)
- Drag-over styling
- Drop handling
- File validation feedback

---

## 5. Recommended Implementation Order

### Week 1: Critical Components (Tier 1)
**Effort**: 6-8 days
**Output**: +2,000-2,500 LOC

```
Day 1-2: BottomPlayerBarUnified.test.tsx (300 LOC)
Day 3: TrackRow.test.tsx (200 LOC)
Day 3-4: PlayerBarV2.test.tsx (250 LOC)
Day 4-5: TrackCard.test.tsx (200 LOC)
Day 5-6: CozyLibraryView.test.tsx (400 LOC)
Day 6-8: EnhancementPaneV2.test.tsx (350 LOC)
```

### Week 2: Quick Wins (Easy Wins)
**Effort**: 3-4 days
**Output**: +1,500-2,000 LOC

```
Day 1: Dialog Components (SettingsDialog, CreatePlaylistDialog) (400 LOC)
Day 2: Navigation Components (SearchBar, ViewToggle, GlobalSearch) (400 LOC)
Day 3: Shared Components (Toast, LoadingSpinner, ProgressiveImage) (400 LOC)
Day 4: Utility Components (EmptyState, DropZone, SkeletonLoader) (300 LOC)
```

### Week 3-4: Library Components (Tier 2)
**Effort**: 8-10 days
**Output**: +2,500-3,500 LOC

```
Day 1-2: AlbumDetailView, ArtistDetailView (500 LOC)
Day 3: TrackListView, DraggableTrackRow, SelectableTrackRow (450 LOC)
Day 4-5: Enhancement pane sub-components (600 LOC)
Day 6-7: Player sub-components (600 LOC)
Day 8-10: Batch actions, Library header, Library routing (500 LOC)
```

### Week 5-6: Services & Hooks
**Effort**: 6-8 days
**Output**: +2,000-2,500 LOC

```
Day 1-2: processingService.test.ts (350 LOC)
Day 3-4: mseStreamingService, RealTimeAnalysisStream (500 LOC)
Day 5-6: useUnifiedWebMAudioPlayer, useWebSocket (500 LOC)
Day 7-8: useDragAndDrop, useLibraryData, useTrackSelection (400 LOC)
```

### Week 7: Context Tests & Fine-tuning
**Effort**: 3-4 days
**Output**: +500-800 LOC

```
Day 1: EnhancementContext.test.tsx (200 LOC)
Day 2: WebSocketContext extended tests (200 LOC)
Day 3-4: Edge cases, error scenarios (200 LOC)
```

---

## 6. Implementation Checklist

### Template for New Tests

Use this structure for consistency:

```tsx
/**
 * ComponentName Tests
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Tests for [Component description]
 *
 * Test Coverage:
 * - Rendering with different props
 * - User interactions (clicks, input, etc.)
 * - State management
 * - Props validation
 * - Error handling
 * - Edge cases
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'
import ComponentName from '../ComponentName'

describe('ComponentName', () => {
  beforeEach(() => {
    // Setup mocks
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render correctly', () => {
      // Test implementation
    })
  })

  describe('Interactions', () => {
    it('should handle user interaction', () => {
      // Test implementation
    })
  })

  describe('State Management', () => {
    it('should update state correctly', async () => {
      // Test implementation
    })
  })

  describe('Props', () => {
    it('should accept and use props', () => {
      // Test implementation
    })
  })

  describe('Error Handling', () => {
    it('should handle errors gracefully', () => {
      // Test implementation
    })
  })

  describe('Edge Cases', () => {
    it('should handle edge case', () => {
      // Test implementation
    })
  })
})
```

---

## 7. Testing Patterns Reference

### Pattern 1: Component Rendering
```tsx
it('renders component correctly', () => {
  render(<Component />)
  expect(screen.getByRole('button', { name: /text/i })).toBeInTheDocument()
})
```

### Pattern 2: User Click
```tsx
it('handles click event', () => {
  const handleClick = vi.fn()
  render(<Component onClick={handleClick} />)
  fireEvent.click(screen.getByRole('button'))
  expect(handleClick).toHaveBeenCalledTimes(1)
})
```

### Pattern 3: Input Change
```tsx
it('handles input change', async () => {
  render(<SearchInput onChange={vi.fn()} />)
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: 'search' } })
  expect(input).toHaveValue('search')
})
```

### Pattern 4: Async Behavior
```tsx
it('loads data asynchronously', async () => {
  render(<AsyncComponent />)
  expect(screen.getByText(/loading/i)).toBeInTheDocument()
  
  await waitFor(() => {
    expect(screen.getByText(/loaded/i)).toBeInTheDocument()
  })
})
```

### Pattern 5: WebSocket Integration
```tsx
it('responds to WebSocket message', async () => {
  const { result } = renderHook(() => useWebSocketContext())
  
  // Simulate WebSocket message
  mockWS.simulateMessage({
    type: 'player_state',
    data: { isPlaying: true }
  })
  
  await waitFor(() => {
    expect(result.current.isPlaying).toBe(true)
  })
})
```

---

## 8. Coverage Goals by Phase

### Current State
- **Overall**: ~45%
- **Components**: 16% (11/67)
- **Hooks**: 31% (4/13)
- **Services**: 55% (6/11)

### After Week 1 (Critical Components)
- **Overall**: ~50%
- **Components**: 25% (17/67)
- **Hooks**: 31% (4/13)
- **Services**: 55% (6/11)

### After Week 2 (Quick Wins)
- **Overall**: ~55%
- **Components**: 35% (24/67)
- **Hooks**: 31% (4/13)
- **Services**: 55% (6/11)

### After Week 4 (All Components)
- **Overall**: ~65%
- **Components**: 65% (44/67)
- **Hooks**: 31% (4/13)
- **Services**: 55% (6/11)

### After Week 6 (Services & Hooks)
- **Overall**: ~70%
- **Components**: 65% (44/67)
- **Hooks**: 75% (10/13)
- **Services**: 90% (10/11)

### Final Target
- **Overall**: 75%+
- **Components**: 75% (50/67)
- **Hooks**: 85% (11/13)
- **Services**: 95% (10/11)

---

## 9. Success Metrics

Track these metrics to measure progress:

```
Week 1:
- [ ] 6 critical components tested
- [ ] 2,000+ LOC added
- [ ] Component coverage: 16% → 25%

Week 2:
- [ ] 10 quick-win components tested
- [ ] 1,500+ LOC added
- [ ] Component coverage: 25% → 35%

Week 4:
- [ ] All high-priority components tested
- [ ] 4,000+ LOC added
- [ ] Component coverage: 35% → 65%

Week 6:
- [ ] All services with tests
- [ ] Most hooks with tests
- [ ] Hook coverage: 31% → 75%
- [ ] Service coverage: 55% → 90%

Final:
- [ ] 8,000+ LOC of new tests
- [ ] Overall coverage: 45% → 70%+
- [ ] All critical components tested
- [ ] All critical services tested
```

---

## 10. Risk Mitigation

### Potential Blockers
1. **Complex component dependencies** - Solution: Test sub-components first
2. **WebSocket/async complexity** - Solution: Use existing mock patterns
3. **Time constraints** - Solution: Focus on Tier 1 + quick wins first
4. **Breaking changes** - Solution: Run tests incrementally
5. **Mock maintenance** - Solution: Reuse existing mock infrastructure

### Quality Assurance
- Run `npm run test:run` after each component test
- Run `npm run test:coverage` weekly to track progress
- Review test patterns with existing tests
- Keep tests focused on behavior, not implementation

---

## Summary

**Current**: 35 files, 16,621 LOC, 750+ tests, 45% coverage
**Target**: +8,000 LOC, 1,200+ tests, 70% coverage
**Timeline**: 6-8 weeks for full implementation
**Effort**: ~30-35 developer days

**Recommended Start**: Begin with 6 critical Tier 1 components (Week 1)

