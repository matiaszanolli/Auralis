# Context Menu System Guide
## Auralis Music Player

**Last Updated**: October 30, 2025
**Status**: ✅ **Phase 2.2 Complete**

---

## Overview

The Auralis context menu system provides right-click and "more" button functionality across all interactive elements (tracks, albums, artists, playlists). It follows consistent patterns for styling, behavior, and accessibility.

---

## Architecture

### Core Components

#### **1. `ContextMenu.tsx`** - Base Context Menu Component

**Location**: [`auralis-web/frontend/src/components/shared/ContextMenu.tsx`](auralis-web/frontend/src/components/shared/ContextMenu.tsx)

Generic reusable context menu component with:
- Position-based anchoring (appears at mouse position)
- Styled menu items with hover effects
- Destructive action styling (red for delete)
- Dividers for visual grouping
- Icon support
- Outside click detection

**Usage**:
```tsx
import { ContextMenu, useContextMenu, getTrackContextActions } from '../shared/ContextMenu';

const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

// In component:
<Box onContextMenu={handleContextMenu}>
  // Your content
</Box>

<ContextMenu
  anchorPosition={contextMenuState.mousePosition}
  open={contextMenuState.isOpen}
  onClose={handleCloseContextMenu}
  actions={contextActions}
/>
```

#### **2. `TrackContextMenu.tsx`** - Specialized Track Context Menu

**Location**: [`auralis-web/frontend/src/components/shared/TrackContextMenu.tsx`](auralis-web/frontend/src/components/shared/TrackContextMenu.tsx)

Enhanced context menu specifically for tracks with:
- **Dynamic playlist list** - loads user playlists
- **Create new playlist** - inline dialog
- **Nested playlist menu** - expandable playlist section
- **All track actions** - play, queue, favorites, navigation, edit, delete

**Usage**:
```tsx
import { TrackContextMenu } from '../shared/TrackContextMenu';

<TrackContextMenu
  trackId={track.id}
  trackTitle={track.title}
  trackAlbumId={track.album_id}
  trackArtistName={track.artist}
  isFavorite={track.favorite}
  anchorPosition={anchorPosition}
  onClose={() => setAnchorPosition(null)}
  onPlay={() => handlePlay(track.id)}
  onAddToQueue={() => handleAddToQueue(track.id)}
  onToggleFavorite={() => handleToggleFavorite(track.id)}
  onShowAlbum={() => navigateToAlbum(track.album_id)}
  onShowArtist={() => navigateToArtist(track.artist)}
  onShowInfo={() => showTrackInfo(track.id)}
  onEditMetadata={() => openEditDialog(track.id)}
  onDelete={() => deleteTrack(track.id)}
/>
```

---

## Context Menu Actions

### Track Actions

**Helper**: `getTrackContextActions(trackId, isLoved, callbacks)`

| Action | Icon | Description | Callback |
|--------|------|-------------|----------|
| **Play Now** | ▶️ | Play track immediately | `onPlay` |
| **Add to Queue** | 🎵 | Add to end of play queue | `onAddToQueue` |
| **Add to Playlist** | ➕ | Add to existing/new playlist | `onAddToPlaylist` |
| **Add to Favourites** | ❤️ | Toggle favorite status | `onToggleLove` |
| **Go to Album** | 💿 | Navigate to album view | `onShowAlbum` |
| **Go to Artist** | 👤 | Navigate to artist view | `onShowArtist` |
| **Track Info** | ℹ️ | Show track details modal | `onShowInfo` |
| **Edit Metadata** | ✏️ | Open metadata editor | `onEditMetadata` |
| **Remove from Library** | 🗑️ | Delete track (destructive) | `onDelete` |

**Example**:
```tsx
const contextActions = getTrackContextActions(trackId, isLoved, {
  onPlay: () => playTrack(trackId),
  onAddToQueue: () => addToQueue(trackId),
  onAddToPlaylist: () => showPlaylistPicker(trackId),
  onToggleLove: () => toggleFavorite(trackId),
  onShowAlbum: () => navigateToAlbum(albumId),
  onShowArtist: () => navigateToArtist(artistName),
  onShowInfo: () => showTrackInfo(trackId),
  onEditMetadata: () => editMetadata(trackId),
  onDelete: () => deleteTrack(trackId),
});
```

---

### Album Actions

**Helper**: `getAlbumContextActions(albumId, callbacks)`

| Action | Icon | Description | Callback |
|--------|------|-------------|----------|
| **Play Album** | ▶️ | Play all tracks in order | `onPlay` |
| **Add to Queue** | 🎵 | Add all tracks to queue | `onAddToQueue` |
| **Go to Artist** | 👤 | Navigate to artist view | `onShowArtist` |
| **Edit Album** | ✏️ | Edit album metadata | `onEdit` |

**Example**:
```tsx
const contextActions = getAlbumContextActions(albumId, {
  onPlay: () => playAlbum(albumId),
  onAddToQueue: () => addAlbumToQueue(albumId),
  onShowArtist: () => navigateToArtist(artist),
  onEdit: () => editAlbum(albumId),
});
```

**Implementation** ([AlbumCard.tsx](auralis-web/frontend/src/components/library/AlbumCard.tsx:142-285)):
```tsx
const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

<StyledCard onContextMenu={handleContextMenu}>
  // Card content
</StyledCard>

<ContextMenu
  anchorPosition={contextMenuState.mousePosition}
  open={contextMenuState.isOpen}
  onClose={handleCloseContextMenu}
  actions={getAlbumContextActions(id, callbacks)}
/>
```

---

### Artist Actions

**Helper**: `getArtistContextActions(artistId, callbacks)`

| Action | Icon | Description | Callback |
|--------|------|-------------|----------|
| **Play All Songs** | ▶️ | Play all artist tracks | `onPlayAll` |
| **Add All to Queue** | 🎵 | Add all tracks to queue | `onAddToQueue` |
| **Show Albums** | 💿 | View all artist albums | `onShowAlbums` |
| **Artist Info** | ℹ️ | Show artist details | `onShowInfo` |

**Example**:
```tsx
const contextActions = getArtistContextActions(artistId, {
  onPlayAll: () => playArtistTracks(artistId),
  onAddToQueue: () => addArtistToQueue(artistId),
  onShowAlbums: () => showArtistAlbums(artistId),
  onShowInfo: () => showArtistInfo(artistId),
});
```

---

### Playlist Actions

**Helper**: `getPlaylistContextActions(playlistId, callbacks)`

| Action | Icon | Description | Callback |
|--------|------|-------------|----------|
| **Play Playlist** | ▶️ | Play all playlist tracks | `onPlay` |
| **Edit Playlist** | ✏️ | Edit playlist metadata | `onEdit` |
| **Delete Playlist** | 🗑️ | Delete playlist (destructive) | `onDelete` |

**Example**:
```tsx
const contextActions = getPlaylistContextActions(playlistId, {
  onPlay: () => playPlaylist(playlistId),
  onEdit: () => editPlaylist(playlistId),
  onDelete: () => deletePlaylist(playlistId),
});
```

---

## Styling & Design

### Visual Design

**Base Styling** ([ContextMenu.tsx](auralis-web/frontend/src/components/shared/ContextMenu.tsx:34-69)):
```tsx
const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: colors.background.secondary,       // Dark navy
    border: '1px solid rgba(102, 126, 234, 0.2)', // Purple border
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',   // Deep shadow
    borderRadius: '8px',
    minWidth: '220px',
    padding: '4px',
    backdropFilter: 'blur(12px)',                  // Glassmorphism
  },
});

const StyledMenuItem = styled(MenuItem)<{ destructive?: boolean }>(({ destructive }) => ({
  borderRadius: '6px',
  padding: '10px 12px',
  margin: '2px 0',
  fontSize: '14px',
  color: destructive ? '#ff4757' : colors.text.primary,
  transition: 'all 0.2s ease',

  '&:hover': {
    background: destructive
      ? 'rgba(255, 71, 87, 0.1)'              // Red hover for delete
      : 'rgba(102, 126, 234, 0.15)',          // Purple hover
    transform: 'translateX(2px)',             // Subtle slide effect
  },
}));
```

### Interaction States

**Normal Item**:
- **Default**: Dark background, white text, gray icon
- **Hover**: Purple background (15% opacity), purple icon, slide right 2px
- **Active**: Same as hover with slight scale down

**Destructive Item** (delete actions):
- **Default**: Dark background, red text, red icon
- **Hover**: Red background (12% opacity), slide right 2px
- **Active**: Same as hover

**Disabled Item**:
- **Default**: Gray text, 50% opacity
- **Hover**: No interaction

---

## Keyboard Shortcuts

Context menus can be triggered with keyboard:

| Key | Action |
|-----|--------|
| **Right-click** | Open context menu at mouse position |
| **Shift + F10** | Open context menu at element center |
| **Context Menu key** | Open context menu at element center |
| **Escape** | Close context menu |
| **Enter** | Execute selected menu item |
| **Arrow Up/Down** | Navigate menu items |

**Implementation pattern**:
```tsx
const handleKeyDown = (e: React.KeyboardEvent) => {
  if (e.key === 'F10' && e.shiftKey) {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const syntheticEvent = {
      preventDefault: () => {},
      stopPropagation: () => {},
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
    } as React.MouseEvent;
    handleContextMenu(syntheticEvent);
  }
};
```

---

## Integration Patterns

### Pattern 1: Simple Context Menu

For basic components (albums, artists):

```tsx
import { useContextMenu, ContextMenu, getAlbumContextActions } from '../shared/ContextMenu';

function AlbumItem({ album }) {
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

  const contextActions = getAlbumContextActions(album.id, {
    onPlay: () => playAlbum(album.id),
    // ... other callbacks
  });

  return (
    <>
      <Box onContextMenu={handleContextMenu}>
        {/* Component content */}
      </Box>

      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      />
    </>
  );
}
```

### Pattern 2: Enhanced Track Context Menu

For tracks with playlist management:

```tsx
import { TrackContextMenu } from '../shared/TrackContextMenu';

function TrackRow({ track }) {
  const [anchorPosition, setAnchorPosition] = useState<{top: number, left: number} | null>(null);

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setAnchorPosition({ top: e.clientY, left: e.clientX });
  };

  return (
    <>
      <Box onContextMenu={handleContextMenu}>
        {/* Track row content */}
      </Box>

      <TrackContextMenu
        trackId={track.id}
        trackTitle={track.title}
        trackAlbumId={track.album_id}
        trackArtistName={track.artist}
        isFavorite={track.favorite}
        anchorPosition={anchorPosition}
        onClose={() => setAnchorPosition(null)}
        onPlay={() => playTrack(track.id)}
        onAddToQueue={() => addToQueue(track.id)}
        onToggleFavorite={() => toggleFavorite(track.id)}
        onShowAlbum={() => navigateToAlbum(track.album_id)}
        onShowArtist={() => navigateToArtist(track.artist)}
        onShowInfo={() => showTrackInfo(track.id)}
        onEditMetadata={() => editMetadata(track.id)}
        onDelete={() => deleteTrack(track.id)}
      />
    </>
  );
}
```

### Pattern 3: "More" Button Integration

For album cards with "more" buttons:

```tsx
const handleMoreClick = (e: React.MouseEvent) => {
  e.stopPropagation();
  // Simulate context menu at button position
  const rect = e.currentTarget.getBoundingClientRect();
  const syntheticEvent = {
    preventDefault: () => {},
    stopPropagation: () => {},
    clientX: rect.right,
    clientY: rect.bottom,
  } as React.MouseEvent;
  handleContextMenu(syntheticEvent);
};

<IconButton onClick={handleMoreClick}>
  <MoreVert />
</IconButton>
```

---

## Accessibility

### ARIA Support

- Context menus use Material-UI `Menu` component with built-in ARIA roles
- Menu items have proper `role="menuitem"` attributes
- Focus management handled automatically
- Keyboard navigation supported out of the box

### Screen Reader Announcements

```tsx
<IconButton
  onClick={handleMoreClick}
  aria-label={`More options for ${title}`}
  aria-haspopup="menu"
>
  <MoreVert />
</IconButton>
```

### Focus Management

- Menu automatically focuses first item on open
- Arrow keys navigate between items
- Escape key closes menu and returns focus
- Tab/Shift+Tab cycle through items

---

## Testing

### Manual Testing Checklist

- [ ] Right-click on track opens context menu
- [ ] Right-click on album opens context menu
- [ ] Right-click on artist opens context menu
- [ ] "More" button opens context menu
- [ ] Context menu appears at correct position
- [ ] Menu closes on outside click
- [ ] Menu closes on Escape key
- [ ] All menu items execute correct actions
- [ ] Destructive actions show red styling
- [ ] Hover effects work properly
- [ ] Keyboard navigation works
- [ ] Screen reader announces menu items

### Unit Testing Pattern

```tsx
import { render, fireEvent, screen } from '@testing-library/react';
import { ContextMenu, getTrackContextActions } from '../ContextMenu';

test('context menu renders with all track actions', () => {
  const onPlay = jest.fn();
  const onQueue = jest.fn();

  const actions = getTrackContextActions(1, false, {
    onPlay,
    onAddToQueue: onQueue,
  });

  render(
    <ContextMenu
      open={true}
      anchorPosition={{ top: 100, left: 100 }}
      onClose={() => {}}
      actions={actions}
    />
  );

  expect(screen.getByText('Play Now')).toBeInTheDocument();
  expect(screen.getByText('Add to Queue')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Play Now'));
  expect(onPlay).toHaveBeenCalledTimes(1);
});
```

---

## Future Enhancements

### Planned Features

1. **Submenu Support** - Multi-level menus for complex actions
2. **Custom Actions** - Allow plugins to add custom menu items
3. **Keyboard Shortcuts Display** - Show shortcuts in menu items (e.g., "Play Now Ctrl+Enter")
4. **Context Menu Positioning** - Smart positioning to avoid screen edges
5. **Touch Support** - Long-press on mobile to open context menu
6. **Recent Actions** - Show recently used actions at top

### Potential Improvements

1. **Animation** - Smooth fade-in/out transitions
2. **Icons** - More expressive icons for all actions
3. **Grouping** - Visual grouping of related actions
4. **Search** - Filter menu items with keyboard input
5. **Tooltips** - Show action descriptions on hover

---

## Common Issues & Solutions

### Issue: Context menu doesn't appear

**Cause**: Missing `onContextMenu` handler or event.preventDefault() not called

**Solution**:
```tsx
const handleContextMenu = (e: React.MouseEvent) => {
  e.preventDefault(); // IMPORTANT: Prevents browser context menu
  e.stopPropagation(); // Optional: Prevents parent handlers
  handleContextMenuBase(e);
};
```

### Issue: Menu appears in wrong position

**Cause**: Incorrect anchor position calculation

**Solution**:
```tsx
// Use e.clientX and e.clientY directly
setAnchorPosition({
  top: e.clientY,
  left: e.clientX,
});
```

### Issue: Menu doesn't close on outside click

**Cause**: Missing `onClose` prop or event handler

**Solution**:
```tsx
<ContextMenu
  open={isOpen}
  onClose={() => setIsOpen(false)} // Must be provided
  // ...
/>
```

---

## API Reference

### `useContextMenu()` Hook

Returns context menu state management:

```tsx
const {
  contextMenuState: {
    isOpen: boolean,
    mousePosition: { top: number, left: number } | undefined
  },
  handleContextMenu: (e: React.MouseEvent) => void,
  handleCloseContextMenu: () => void,
} = useContextMenu();
```

### `ContextMenuAction` Interface

```tsx
interface ContextMenuAction {
  id: string;                    // Unique identifier
  label: string;                 // Display text
  icon?: React.ReactNode;        // Optional icon
  divider?: boolean;             // Show divider before item
  destructive?: boolean;         // Red styling for delete actions
  disabled?: boolean;            // Gray out and disable
  onClick: () => void;           // Action callback
}
```

### Context Action Helpers

```tsx
// Track actions
getTrackContextActions(
  trackId: number,
  isLoved: boolean,
  callbacks: {
    onPlay?: () => void;
    onAddToQueue?: () => void;
    onAddToPlaylist?: () => void;
    onToggleLove?: () => void;
    onEditMetadata?: () => void;
    onShowAlbum?: () => void;
    onShowArtist?: () => void;
    onShowInfo?: () => void;
    onDelete?: () => void;
  }
): ContextMenuAction[]

// Album actions
getAlbumContextActions(
  albumId: number,
  callbacks: {
    onPlay?: () => void;
    onAddToQueue?: () => void;
    onShowArtist?: () => void;
    onEdit?: () => void;
  }
): ContextMenuAction[]

// Artist actions
getArtistContextActions(
  artistId: number,
  callbacks: {
    onPlayAll?: () => void;
    onAddToQueue?: () => void;
    onShowAlbums?: () => void;
    onShowInfo?: () => void;
  }
): ContextMenuAction[]

// Playlist actions
getPlaylistContextActions(
  playlistId: string,
  callbacks: {
    onPlay?: () => void;
    onEdit?: () => void;
    onDelete?: () => void;
  }
): ContextMenuAction[]
```

---

## Conclusion

The Auralis context menu system provides a consistent, accessible, and visually polished way to expose actions across all interactive elements. By following the patterns and guidelines in this document, developers can easily integrate context menus into new components while maintaining consistency with the rest of the application.

**Key Takeaways**:
- Use `useContextMenu()` hook for state management
- Use helper functions (`getTrackContextActions`, etc.) for consistency
- Always call `event.preventDefault()` in context menu handlers
- Mark destructive actions with `destructive: true`
- Test keyboard navigation and screen reader support

---

**Last Updated**: October 30, 2025
**Maintainer**: Auralis Development Team
**Questions?**: See [UI/UX Improvement Roadmap](docs/roadmaps/UI_UX_IMPROVEMENT_ROADMAP.md)
