# Drag and Drop Integration Guide

**Status**: Phase 2.3 - Drag and Drop infrastructure complete ✅
**Date**: October 30, 2025
**Library**: @hello-pangea/dnd (v18.0.1)

## Overview

This guide documents the drag-and-drop system implemented for Auralis, enabling intuitive track management through drag-and-drop interactions.

## Architecture

### Core Components

#### 1. **DragDropContext** (ComfortableApp.tsx)
The top-level context provider that wraps the entire application and handles all drag-and-drop events.

```tsx
import { DragDropContext, DropResult } from '@hello-pangea/dnd';

<DragDropContext onDragEnd={handleDragEnd}>
  {/* Entire app content */}
</DragDropContext>
```

**Handler Logic:**
```tsx
const handleDragEnd = useCallback((result: DropResult) => {
  const { source, destination, draggableId } = result;

  if (!destination) return; // Dropped outside
  if (source.droppableId === destination.droppableId &&
      source.index === destination.index) return; // Same position

  const trackId = parseInt(draggableId.replace('track-', ''), 10);

  // Route to appropriate handler based on destination
  if (destination.droppableId === 'queue') {
    // Add to queue
  } else if (destination.droppableId.startsWith('playlist-')) {
    // Add to playlist
  } else {
    // Reorder within same list
  }
}, []);
```

#### 2. **DraggableTrackRow** (library/DraggableTrackRow.tsx)
Wrapper component that makes TrackRow draggable.

**Features:**
- Drag handle with visual indicator
- Opacity change during drag (0.5)
- Supports all TrackRow props
- Can disable dragging per-track
- Optional drag handle visibility

**Usage:**
```tsx
<DraggableTrackRow
  track={track}
  index={index}
  draggableId={`track-${track.id}`}
  showDragHandle={true}
  isDragDisabled={false}
  onPlay={handlePlay}
  // ... all TrackRow props
/>
```

#### 3. **DroppablePlaylist** (playlist/DroppablePlaylist.tsx)
Playlist item that accepts track drops.

**Features:**
- Visual highlight on drag-over (dashed border + background)
- Drop indicator overlay
- Maintains playlist selection state
- Context menu support

**Usage:**
```tsx
<DroppablePlaylist
  playlistId={playlist.id}
  playlistName={playlist.name}
  trackCount={playlist.track_count}
  selected={selectedPlaylistId === playlist.id}
  onClick={handleClick}
  onContextMenu={handleContextMenu}
/>
```

#### 4. **DroppableQueue** (player/DroppableQueue.tsx)
Queue area that accepts track drops and supports reordering.

**Features:**
- Visual feedback on drag-over
- Empty state with instructions
- Reorderable track list
- Scrollable container

**Usage:**
```tsx
<DroppableQueue
  queueLength={queue.length}
  showHeader={true}
>
  {queue.map((track, index) => (
    <DraggableTrackRow key={track.id} ... />
  ))}
</DroppableQueue>
```

#### 5. **DraggablePlaylistView** (playlist/DraggablePlaylistView.tsx)
Example component demonstrating full drag-and-drop integration for playlist editing.

**Features:**
- Complete playlist track management
- Drag to reorder within playlist
- Visual feedback during drag
- API integration for persistence

### Utility Hooks

#### useDragAndDrop.ts

**State Management:**
```tsx
interface DragDropState {
  isDragging: boolean;
  draggedItemId: string | null;
  draggedItemType: 'track' | 'playlist' | null;
}
```

**Helper Functions:**
```tsx
// Reorder items within a list
reorder(list, startIndex, endIndex);

// Move item between lists
move(sourceList, destList, source, destination);

// Get styled drag handle props
getDragHandleProps(isDragging);

// Get styled droppable props
getDroppableProps(isDraggingOver, isDraggingItem);
```

## Integration Patterns

### Pattern 1: Draggable Track List

For any track list that should support dragging:

```tsx
import { Droppable } from '@hello-pangea/dnd';
import { DraggableTrackRow } from './library/DraggableTrackRow';

<Droppable droppableId="track-list" type="TRACK">
  {(provided, snapshot) => (
    <Box
      ref={provided.innerRef}
      {...provided.droppableProps}
      sx={{
        background: snapshot.isDraggingOver
          ? 'rgba(102, 126, 234, 0.05)'
          : 'transparent'
      }}
    >
      {tracks.map((track, index) => (
        <DraggableTrackRow
          key={track.id}
          track={track}
          index={index}
          draggableId={`track-${track.id}`}
          onPlay={handlePlay}
        />
      ))}
      {provided.placeholder}
    </Box>
  )}
</Droppable>
```

**Key Points:**
- Always provide unique `draggableId` (e.g., `track-${track.id}`)
- Include `{provided.placeholder}` for proper layout
- Use `snapshot.isDraggingOver` for visual feedback

### Pattern 2: Droppable Playlist Sidebar

For playlists that accept drops:

```tsx
import { DroppablePlaylist } from './playlist/DroppablePlaylist';

playlists.map((playlist) => (
  <DroppablePlaylist
    key={playlist.id}
    playlistId={playlist.id}
    playlistName={playlist.name}
    trackCount={playlist.track_count}
  />
))
```

**Automatic Features:**
- Drop zone highlighting
- Visual indicator on drag-over
- Hidden placeholder for proper spacing

### Pattern 3: Reorderable Playlist Content

For editing playlist track order:

```tsx
const handleDragEnd = (result: DropResult) => {
  if (!result.destination) return;

  const reorderedTracks = reorder(
    tracks,
    result.source.index,
    result.destination.index
  );

  setTracks(reorderedTracks);
  // Persist to API
};

<Droppable droppableId={`playlist-${playlistId}`}>
  {(provided) => (
    <Box ref={provided.innerRef} {...provided.droppableProps}>
      {tracks.map((track, index) => (
        <DraggableTrackRow
          key={track.id}
          track={track}
          index={index}
          draggableId={`track-${track.id}`}
          showDragHandle={true}
        />
      ))}
      {provided.placeholder}
    </Box>
  )}
</Droppable>
```

## Backend API Integration

### Required Endpoints

#### 1. Add Track to Playlist
```typescript
POST /api/playlists/{playlistId}/tracks
Body: { track_id: number, position?: number }
```

#### 2. Reorder Playlist Track
```typescript
PUT /api/playlists/{playlistId}/tracks/{trackId}/position
Body: { from_index: number, to_index: number }
```

#### 3. Add Track to Queue
```typescript
POST /api/player/queue
Body: { track_id: number, position?: number }
```

#### 4. Reorder Queue
```typescript
PUT /api/player/queue/reorder
Body: { from_index: number, to_index: number }
```

### Example API Call
```typescript
const handleTrackToPlaylist = async (trackId: number, playlistId: number, position: number) => {
  try {
    await playlistService.addTrackToPlaylist(playlistId, trackId, position);
    success('Track added to playlist');
  } catch (err) {
    error('Failed to add track');
  }
};
```

## Visual Design System

### Colors
```typescript
// Drag-over highlight
background: 'rgba(102, 126, 234, 0.1)'

// Dashed border during drag
border: '2px dashed rgba(102, 126, 234, 0.5)'

// Dragging item opacity
opacity: 0.5

// Accent color
primary: '#667eea'
```

### Animations
```typescript
transition: 'all 0.2s ease'

// Drag handle
cursor: isDragging ? 'grabbing' : 'grab'
opacity: isDragging ? 0.5 : 1
```

## Testing Checklist

### Functional Tests
- [ ] Drag track to playlist adds track
- [ ] Drag track to queue adds to queue
- [ ] Reorder within playlist works
- [ ] Reorder within queue works
- [ ] Drop outside droppable cancels
- [ ] Drop at same position is no-op
- [ ] Multiple tracks can be dragged sequentially
- [ ] Drag handle is clickable
- [ ] Track actions still work (play, context menu)

### Visual Tests
- [ ] Drag handle appears on hover
- [ ] Opacity changes during drag
- [ ] Drop zones highlight on drag-over
- [ ] Drop indicator shows correct position
- [ ] Animations are smooth (0.2s)
- [ ] Empty state shows instructions
- [ ] Playlist counter updates after drop

### Edge Cases
- [ ] Drag with empty queue
- [ ] Drag to empty playlist
- [ ] Drag currently playing track
- [ ] Drag with search filter active
- [ ] Drag with infinite scroll (complex)
- [ ] Multiple rapid drags
- [ ] Cancel drag with Escape key

## Performance Considerations

### Optimization Strategies

1. **Virtual Scrolling**: For large track lists (1000+ items), use react-virtualized or similar
2. **Memoization**: Memoize drag handlers with `useCallback`
3. **Debouncing**: Debounce API calls for rapid reordering
4. **Optimistic Updates**: Update UI immediately, sync with backend asynchronously
5. **Placeholder Sizing**: Use fixed heights for smooth dragging

```tsx
// Optimistic reorder with rollback
const handleReorder = async (fromIndex, toIndex) => {
  const newOrder = reorder(tracks, fromIndex, toIndex);
  setTracks(newOrder); // Immediate UI update

  try {
    await api.reorder(fromIndex, toIndex);
  } catch (err) {
    setTracks(tracks); // Rollback on error
    error('Failed to reorder');
  }
};
```

## Browser Compatibility

- ✅ Chrome/Edge (Chromium) - Full support
- ✅ Firefox - Full support
- ✅ Safari - Full support
- ⚠️ Mobile - Touch support included, but test thoroughly
- ❌ IE11 - Not supported (@hello-pangea/dnd requires modern browser)

## Known Limitations

1. **Infinite Scroll Integration**: Complex - requires careful handling of dynamic item counts
2. **Multi-Select Drag**: Not yet implemented (requires additional state management)
3. **Cross-Window Drag**: Not supported by library
4. **Nested Droppables**: Requires careful `type` management to avoid conflicts

## Future Enhancements

### Phase 2.3.1: Multi-Select Drag (Planned)
- Select multiple tracks with Ctrl/Cmd + click
- Drag multiple tracks at once
- Visual indicator for selected count

### Phase 2.3.2: Drag Animation Polish (Planned)
- Custom drag preview with track artwork
- Smooth spring animations
- Drag trajectory visualization

### Phase 2.3.3: Advanced Gestures (Planned)
- Swipe to add to queue (mobile)
- Long-press to enable drag (mobile)
- Pinch to select multiple (mobile)

## Component File Reference

```
auralis-web/frontend/src/
├── ComfortableApp.tsx                         # DragDropContext wrapper
├── hooks/
│   └── useDragAndDrop.ts                      # Utilities and helpers
├── components/
│   ├── library/
│   │   ├── DraggableTrackRow.tsx              # Draggable track wrapper
│   │   └── TrackRow.tsx                       # Base track component
│   ├── playlist/
│   │   ├── DroppablePlaylist.tsx              # Droppable playlist item
│   │   ├── DraggablePlaylistView.tsx          # Example playlist editor
│   │   └── PlaylistList.tsx                   # Sidebar playlists
│   └── player/
│       └── DroppableQueue.tsx                 # Droppable queue area
```

## Quick Start Example

**Minimal working example:**

```tsx
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';

function SimpleDragList() {
  const [items, setItems] = useState(['Item 1', 'Item 2', 'Item 3']);

  const onDragEnd = (result) => {
    if (!result.destination) return;

    const newItems = Array.from(items);
    const [removed] = newItems.splice(result.source.index, 1);
    newItems.splice(result.destination.index, 0, removed);

    setItems(newItems);
  };

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <Droppable droppableId="list">
        {(provided) => (
          <div ref={provided.innerRef} {...provided.droppableProps}>
            {items.map((item, index) => (
              <Draggable key={item} draggableId={item} index={index}>
                {(provided) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.draggableProps}
                    {...provided.dragHandleProps}
                  >
                    {item}
                  </div>
                )}
              </Draggable>
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </DragDropContext>
  );
}
```

## Support and Resources

- **Library Docs**: https://github.com/hello-pangea/dnd
- **Examples**: See `DraggablePlaylistView.tsx` for complete implementation
- **API Pattern**: Follow `reorder()` and `move()` utilities in `useDragAndDrop.ts`

---

**Next Steps:**
1. Implement backend API endpoints
2. Integrate draggable tracks in CozyLibraryView
3. Add queue reordering in player
4. Test with large libraries (1000+ tracks)
5. Add multi-select drag support
