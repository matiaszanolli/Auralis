# UI Components Checklist

Track your progress building the new Auralis UI components.

---

## Foundation (Phase 1)

### Theme & Styles
- [ ] `src/theme/auralisTheme.ts` - Main theme with colors and gradients
- [ ] `src/styles/globalStyles.ts` - Global CSS and animations
- [ ] `src/index.tsx` - Updated to use ThemeProvider

### Shared Components
- [ ] `src/components/shared/GradientButton.tsx` - Aurora gradient button
- [ ] `src/components/shared/GradientSlider.tsx` - Gradient slider control
- [ ] `src/components/shared/GlowCard.tsx` - Card with hover glow
- [ ] `src/components/shared/LoadingSpinner.tsx` - Aurora spinner
- [ ] `src/components/shared/Toast.tsx` - Notification toast
- [ ] `src/components/shared/EmptyState.tsx` - Empty state component
- [ ] `src/components/shared/ContextMenu.tsx` - Right-click menu

---

## Core Components (Phase 2)

### Library Components
- [ ] `src/components/library/AlbumCard.tsx` - Album artwork card
- [ ] `src/components/library/TrackRow.tsx` - Compact track row
- [ ] `src/components/library/TrackListView.tsx` - List view container
- [ ] `src/components/library/AlbumGridView.tsx` - Grid view container

### Player Components
- [ ] `src/components/player/TrackQueue.tsx` - Bottom track queue (NEW!)
- [ ] `src/components/player/ProgressBar.tsx` - Gradient progress bar
- [ ] `src/components/player/VolumeControl.tsx` - Gradient volume slider
- [ ] `src/components/player/PlaybackControls.tsx` - Play/pause/skip controls

### Navigation Components
- [ ] `src/components/navigation/SearchBar.tsx` - Pill-shaped search
- [ ] `src/components/navigation/ViewToggle.tsx` - Grid/list toggle
- [ ] `src/components/navigation/AuroraLogo.tsx` - Gradient logo

---

## Enhanced Existing Components (Phase 2)

### Update These Files
- [ ] `src/components/Sidebar.tsx`
  - [ ] Add aurora gradient logo
  - [ ] Active state with border-left accent
  - [ ] Smooth hover transitions
  - [ ] Better spacing (40px items)

- [ ] `src/components/BottomPlayerBar.tsx`
  - [ ] Aurora gradient play button
  - [ ] Gradient progress bar
  - [ ] 60x60px album art
  - [ ] Gradient volume slider
  - [ ] Magic toggle styling

- [ ] `src/components/PresetPane.tsx`
  - [ ] Gradient toggle switch
  - [ ] Dark styled dropdown
  - [ ] Gradient intensity slider
  - [ ] Uppercase labels

- [ ] `src/components/CozyLibraryView.tsx`
  - [ ] Use new AlbumCard
  - [ ] Integrate SearchBar
  - [ ] Add TrackQueue below grid
  - [ ] EmptyState when no tracks

---

## Advanced Features (Phase 3)

### Interactive Components
- [ ] `src/components/modals/TrackInfoModal.tsx` - Track details
- [ ] `src/components/modals/AddToPlaylistModal.tsx` - Playlist selector
- [ ] `src/components/modals/ScanFolderModal.tsx` - Folder scanner
- [ ] `src/components/menus/TrackContextMenu.tsx` - Track right-click
- [ ] `src/components/menus/AlbumContextMenu.tsx` - Album right-click

### State Management
- [ ] `src/hooks/usePlayback.ts` - Playback state hook
- [ ] `src/hooks/useLibrary.ts` - Library state hook
- [ ] `src/hooks/useQueue.ts` - Queue state hook
- [ ] `src/hooks/useWebSocket.ts` - WebSocket connection (exists, may need updates)

---

## Visual Polish (Phase 4)

### Animations
- [ ] Hover animations on cards
- [ ] Smooth transitions everywhere
- [ ] Loading skeleton screens
- [ ] Toast slide-in animations
- [ ] Context menu fade-in
- [ ] Playlist expand/collapse

### Loading States
- [ ] Album card skeleton
- [ ] Track row skeleton
- [ ] Sidebar skeleton
- [ ] Player bar skeleton

---

## Component Status Summary

| Component | Status | Priority | Notes |
|-----------|--------|----------|-------|
| AlbumCard | 🔄 In Progress | High | Core visual element |
| TrackQueue | 📋 Not Started | High | Key feature from screenshot |
| GradientButton | ✅ Ready | High | Foundation component |
| BottomPlayerBar | 🔄 Needs Enhancement | High | Visible player control |
| SearchBar | 📋 Not Started | Medium | UI polish |
| ContextMenu | 📋 Not Started | Medium | User interaction |
| EmptyState | 📋 Not Started | Medium | Better UX |
| LoadingSpinner | 📋 Not Started | Low | Polish |

Legend:
- ✅ Complete and tested
- 🔄 In progress or needs updates
- 📋 Not started

---

## Quick Reference: Component Specs

### AlbumCard
- Size: 160x160px minimum
- Hover: scale(1.05), glow effect
- Play button overlay on hover
- Title + artist below

### TrackQueue
- Row height: 48px
- Track number | Title | Duration
- Current track highlighted
- Below main content grid

### SearchBar
- Height: 48px
- Pill shape (border-radius: 24px)
- Semi-transparent background
- Search icon left

### BottomPlayerBar
- Height: 80-100px
- Album art: 60x60px
- Gradient play button (large)
- Gradient progress bar
- Volume slider right

### Sidebar
- Width: 240px
- Item height: 40px
- Active: border-left 4px accent
- Hover: background #1a1f3a

---

## Testing Checklist

Once components are built:

- [ ] Visual regression tests
- [ ] Responsive on all screen sizes
- [ ] Keyboard navigation works
- [ ] Screen reader compatible
- [ ] 60fps animations
- [ ] No layout shifts
- [ ] Fast interaction (<100ms)
- [ ] Memory efficient

---

## Documentation

For each component, document:
- [ ] Props interface
- [ ] Usage examples
- [ ] Visual screenshot
- [ ] Storybook story (if using Storybook)

---

**Last Updated**: 2025-10-15
**Total Components**: 35
**Completed**: 0
**In Progress**: 2
**Remaining**: 33
