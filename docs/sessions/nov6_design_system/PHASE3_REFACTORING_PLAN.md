# Phase 3: Large Component Refactoring Plan

**Date**: November 6, 2025
**Status**: 🚧 IN PROGRESS
**Target**: Split 2 large components into focused subcomponents

## Overview

Two components exceed maintainability thresholds and need refactoring:

1. **CozyLibraryView.tsx** - 958 lines (target: <300 lines each)
2. **SettingsDialog.tsx** - 709 lines (target: <200 lines each)

**Goal**: Extract logical sections into focused, reusable subcomponents while maintaining all functionality.

## Component 1: CozyLibraryView.tsx Analysis

### Current State
- **Lines**: 958 (320% over guideline)
- **Responsibilities**: Too many!
  - Library data fetching & pagination
  - Track searching & filtering
  - Batch operations (multi-select)
  - View mode switching (grid/list)
  - Album/artist navigation
  - Track playback controls
  - Folder scanning
  - Metadata editing
  - Infinite scroll management
  - Keyboard shortcuts

### Identified Sections

#### 1. Data Layer (Lines 100-304)
**Extract to**: `hooks/useLibraryData.ts`
- `fetchTracks()` - Initial data loading
- `loadMore()` - Infinite scroll pagination
- `handleScanFolder()` - Folder scanning
- `loadMockData()` - Fallback mock data
- State: `tracks`, `loading`, `hasMore`, `totalTracks`, `offset`

**Lines**: ~205 lines → Custom hook

#### 2. View Routing (Lines 489-590)
**Extract to**: `library/LibraryViewRouter.tsx`
- Album detail routing (lines 489-505)
- Album grid view (lines 508-535)
- Artist list/detail routing (lines 538-590)

**Lines**: ~100 lines → Separate component

#### 3. Track List View (Lines 678-915)
**Extract to**: `library/TrackListView.tsx`
- Grid view rendering (lines 698-811)
- List view rendering (lines 813-914)
- Loading skeletons
- Infinite scroll trigger
- Virtual spacers

**Lines**: ~238 lines → Separate component

#### 4. Empty States (Lines 917-936)
**Extract to**: `library/LibraryEmptyState.tsx`
- Favorites empty state
- Search no results
- Library empty state

**Lines**: ~20 lines → Separate component (already small, but good for clarity)

#### 5. Main Orchestrator (Remaining)
**Keep in**: `CozyLibraryView.tsx`
- Search/filter logic (lines 350-361)
- Batch action handlers (lines 422-486)
- Keyboard shortcuts (lines 320-347)
- Layout/header rendering (lines 593-677)
- Component composition

**Lines**: ~150-200 lines (manageable)

### Refactoring Strategy

```
CozyLibraryView.tsx (958 lines)
├─> hooks/useLibraryData.ts (~200 lines) - Data fetching & pagination
├─> library/LibraryViewRouter.tsx (~100 lines) - Album/artist routing
├─> library/TrackListView.tsx (~240 lines) - Grid/list rendering
├─> library/LibraryEmptyState.tsx (~20 lines) - Empty states
└─> CozyLibraryView.tsx (~150-200 lines) - Main orchestrator
```

**Result**: 958 → 5 focused components (150-240 lines each)

## Component 2: SettingsDialog.tsx Analysis

### Current State (Need to read file first)
- **Lines**: 709
- **Structure**: Tab-based settings dialog
- **Expected sections**: 7 tab components (from audit)

### Analysis Required
Will read and analyze after CozyLibraryView refactoring is complete.

## Implementation Order

### Step 1: Extract useLibraryData Hook ✅ NEXT
```typescript
// hooks/useLibraryData.ts
export const useLibraryData = (view: string) => {
  // State
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [scanning, setScanning] = useState(false);

  // Methods
  const fetchTracks = async (resetPagination = true) => { /* ... */ };
  const loadMore = async () => { /* ... */ };
  const handleScanFolder = async () => { /* ... */ };

  return {
    tracks,
    loading,
    hasMore,
    totalTracks,
    isLoadingMore,
    scanning,
    fetchTracks,
    loadMore,
    handleScanFolder
  };
};
```

### Step 2: Extract LibraryViewRouter Component
```typescript
// library/LibraryViewRouter.tsx
interface LibraryViewRouterProps {
  view: string;
  selectedAlbumId: number | null;
  selectedArtistId: number | null;
  selectedArtistName: string;
  onBack: () => void;
  onAlbumClick: (albumId: number) => void;
  onArtistClick: (artistId: number, artistName: string) => void;
  // ... other props
}

export const LibraryViewRouter: React.FC<LibraryViewRouterProps> = (props) => {
  // Album detail routing
  if (props.selectedAlbumId !== null) {
    return <AlbumDetailView {...albumDetailProps} />;
  }

  // Album grid view
  if (props.view === 'albums') {
    return <AlbumGridView {...albumGridProps} />;
  }

  // Artist views
  if (props.view === 'artists') {
    if (props.selectedArtistId !== null) {
      return <ArtistDetailView {...artistDetailProps} />;
    }
    return <ArtistListView {...artistListProps} />;
  }

  // Return null for track view (handled by parent)
  return null;
};
```

### Step 3: Extract TrackListView Component
```typescript
// library/TrackListView.tsx
interface TrackListViewProps {
  tracks: Track[];
  viewMode: ViewMode;
  loading: boolean;
  hasMore: boolean;
  totalTracks: number;
  isLoadingMore: boolean;
  currentTrackId?: number;
  isPlaying: boolean;
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  onToggleSelect: (trackId: number, e: React.MouseEvent) => void;
  onTrackPlay: (track: Track) => void;
  onEditMetadata: (trackId: number) => void;
  onLoadMore: () => void;
}

export const TrackListView: React.FC<TrackListViewProps> = (props) => {
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Infinite scroll observer
  useEffect(() => {
    // ... observer logic
  }, [props.hasMore, props.isLoadingMore, props.onLoadMore]);

  // Render grid or list view
  if (props.viewMode === 'grid') {
    return <GridView {...props} loadMoreRef={loadMoreRef} />;
  }

  return <ListView {...props} loadMoreRef={loadMoreRef} />;
};
```

### Step 4: Extract LibraryEmptyState Component
```typescript
// library/LibraryEmptyState.tsx
interface LibraryEmptyStateProps {
  view: string;
  searchQuery: string;
  scanning: boolean;
  onScanFolder: () => void;
}

export const LibraryEmptyState: React.FC<LibraryEmptyStateProps> = (props) => {
  if (props.view === 'favourites') {
    return (
      <EmptyState
        icon="music"
        title="No favorites yet"
        description="Click the heart icon on tracks you love"
      />
    );
  }

  if (props.searchQuery) {
    return <NoSearchResults query={props.searchQuery} />;
  }

  return (
    <EmptyLibrary
      onScanFolder={props.onScanFolder}
      scanning={props.scanning}
    />
  );
};
```

### Step 5: Refactor CozyLibraryView to Orchestrator
```typescript
// CozyLibraryView.tsx (new structure)
const CozyLibraryView: React.FC<CozyLibraryViewProps> = ({ view }) => {
  // Use extracted data hook
  const {
    tracks,
    loading,
    hasMore,
    totalTracks,
    isLoadingMore,
    scanning,
    fetchTracks,
    loadMore,
    handleScanFolder
  } = useLibraryData(view);

  // Local UI state (search, selection, navigation)
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);
  const [selectedArtistId, setSelectedArtistId] = useState<number | null>(null);
  // ... other UI state

  // Track selection hook
  const { selectedTracks, isSelected, toggleTrack, ... } = useTrackSelection(filteredTracks);

  // Filtered tracks (search)
  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) return tracks;
    return tracks.filter(/* search logic */);
  }, [searchQuery, tracks]);

  // Keyboard shortcuts
  useEffect(() => {
    // Ctrl+A, Escape handlers
  }, [filteredTracks, hasSelection]);

  // Batch action handlers
  const handleBulkAddToQueue = async () => { /* ... */ };
  const handleBulkAddToPlaylist = async () => { /* ... */ };
  const handleBulkRemove = async () => { /* ... */ };

  // Check if showing routed view (albums/artists)
  const routedView = (
    <LibraryViewRouter
      view={view}
      selectedAlbumId={selectedAlbumId}
      selectedArtistId={selectedArtistId}
      onBack={() => setSelectedAlbumId(null)}
      onAlbumClick={setSelectedAlbumId}
      onArtistClick={(id, name) => {
        setSelectedArtistId(id);
        setSelectedArtistName(name);
      }}
    />
  );

  if (routedView) return routedView;

  // Main track list view
  return (
    <>
      <BatchActionsToolbar ... />
      <Container maxWidth="xl">
        {/* Header */}
        <LibraryHeader view={view} />

        {/* Search & Controls */}
        <LibraryControls
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onScanFolder={handleScanFolder}
          onRefresh={fetchTracks}
          scanning={scanning}
          loading={loading}
          trackCount={filteredTracks.length}
        />

        {/* Track List or Empty State */}
        {filteredTracks.length === 0 && !loading ? (
          <LibraryEmptyState
            view={view}
            searchQuery={searchQuery}
            scanning={scanning}
            onScanFolder={handleScanFolder}
          />
        ) : (
          <TrackListView
            tracks={filteredTracks}
            viewMode={viewMode}
            loading={loading}
            hasMore={hasMore}
            totalTracks={totalTracks}
            isLoadingMore={isLoadingMore}
            selectedTracks={selectedTracks}
            isSelected={isSelected}
            onToggleSelect={toggleTrack}
            onTrackPlay={handlePlayTrack}
            onEditMetadata={handleEditMetadata}
            onLoadMore={loadMore}
          />
        )}
      </Container>
    </>
  );
};
```

**Result**: 958 lines → 150-200 lines orchestrator + 4 focused components

## Benefits of Refactoring

### Maintainability
- ✅ Each component has single clear responsibility
- ✅ Easier to understand and modify
- ✅ Better code organization

### Reusability
- ✅ `useLibraryData` hook can be used in other views
- ✅ `TrackListView` can be reused for playlists
- ✅ `LibraryEmptyState` handles all empty scenarios

### Testability
- ✅ Smaller components = easier to test
- ✅ Hook logic can be tested independently
- ✅ UI components can be tested in isolation

### Performance
- ✅ React.memo opportunities on subcomponents
- ✅ Reduced re-renders (smaller component trees)
- ✅ Better code splitting potential

## Testing Strategy

### Before Refactoring
```bash
# Verify current functionality works
npm run dev
# Test: Load library, search, infinite scroll, batch operations
```

### After Each Extraction
```bash
# Verify no regressions
npm run build
# Test same functionality
```

### Final Verification
```bash
# Ensure all features work
- [ ] Library loads with pagination
- [ ] Search filters correctly
- [ ] Infinite scroll loads more tracks
- [ ] Batch selection works
- [ ] Album/artist navigation works
- [ ] Folder scanning works
- [ ] Grid/list view toggle works
- [ ] Empty states display correctly
```

## Next: SettingsDialog.tsx

After CozyLibraryView refactoring is complete, will analyze and refactor SettingsDialog.tsx (709 lines) into tab-based components.

**Expected structure**:
```
SettingsDialog.tsx (709 lines)
├─> settings/GeneralSettingsTab.tsx
├─> settings/AudioSettingsTab.tsx
├─> settings/LibrarySettingsTab.tsx
├─> settings/AppearanceSettingsTab.tsx
├─> settings/KeyboardShortcutsTab.tsx
├─> settings/AdvancedSettingsTab.tsx
└─> SettingsDialog.tsx (orchestrator)
```

## Success Criteria

### Phase 3 Goals
- [ ] CozyLibraryView: 958 → <300 lines (5 components)
- [ ] SettingsDialog: 709 → <200 lines (7+ components)
- [ ] Zero breaking changes
- [ ] All tests passing
- [ ] Component count: 71 → 80-85 (net +10-15 focused components)

### Quality Metrics
- [ ] No component over 300 lines
- [ ] Each component has single responsibility
- [ ] All extracted components are reusable
- [ ] Props interfaces are well-typed
- [ ] Documentation updated

---

**Ready to begin**: Starting with Step 1 - Extract useLibraryData hook
