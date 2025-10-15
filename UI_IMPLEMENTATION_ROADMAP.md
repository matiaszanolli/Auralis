# UI Implementation Roadmap

**Goal**: Transform current UI to match target design (iTunes/Rhythmbox aesthetic with Spotify/Cider modern touches)

**Target Screenshot Reference**: Neon/aurora themed music player with dark navy backgrounds, large album art grid, and bottom track queue

---

## Phase 1: Design System Foundation (Week 1)

### 1.1 Create Theme System
**File**: `auralis-web/frontend/src/theme/auralisTheme.ts`

**Tasks**:
- [ ] Define Material-UI custom theme
- [ ] Set up color palette (navy, aurora gradients, neon accents)
- [ ] Configure typography system (system fonts, sizing)
- [ ] Create reusable gradient definitions
- [ ] Set up component style overrides for MUI components

**Color System**:
```typescript
const colors = {
  background: {
    primary: '#0A0E27',    // Deep navy
    secondary: '#1a1f3a',  // Lighter navy
    surface: '#252b45',    // Surface elements
  },
  text: {
    primary: '#ffffff',
    secondary: '#8b92b0',
    disabled: '#5a5f7a',
  },
  accent: {
    aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    success: '#00d4aa',
    error: '#ff4757',
    warning: '#ffa502',
  },
  neon: {
    pink: '#ff6b9d',
    purple: '#c44569',
    blue: '#4b7bec',
    cyan: '#26de81',
  }
}
```

### 1.2 Create Global Styles
**File**: `auralis-web/frontend/src/styles/globalStyles.ts`

**Tasks**:
- [ ] Define CSS custom properties for gradients
- [ ] Create animation keyframes (pulse, glow, slide)
- [ ] Set up smooth transitions
- [ ] Define scrollbar styling
- [ ] Create utility classes for common patterns

### 1.3 Create Shared Components
**Files**: `auralis-web/frontend/src/components/shared/`

**Components to build**:
- [ ] `GradientButton.tsx` - Aurora gradient button
- [ ] `GradientSlider.tsx` - Custom slider with gradient track
- [ ] `GlowCard.tsx` - Card with hover glow effect
- [ ] `LoadingSpinner.tsx` - Aurora gradient spinner
- [ ] `Toast.tsx` - Notification toast component

---

## Phase 2: Core UI Components (Week 2)

### 2.1 AlbumCard Component
**File**: `auralis-web/frontend/src/components/library/AlbumCard.tsx`

**Requirements from target design**:
- 160x160px minimum artwork size
- Border radius: 8px
- Hover: scale(1.05) with subtle glow
- Title below artwork (white, 16px)
- Artist/author below title (gray, 14px)
- Play button overlay on hover
- Optional quality badge (top-right corner)

**Props**:
```typescript
interface AlbumCardProps {
  id: number;
  title: string;
  artist: string;
  albumArt: string;
  trackCount?: number;
  quality?: number;
  onPlay: (id: number) => void;
  onContextMenu?: (id: number, event: React.MouseEvent) => void;
}
```

### 2.2 TrackRow Component
**File**: `auralis-web/frontend/src/components/library/TrackRow.tsx`

**Requirements from target design**:
- Row height: 48px
- Columns: Track # | Title | Artist | Album | Duration
- Hover: Background change to #1a1f3a
- Current track: Highlighted with accent
- Double-click to play
- Right-click for context menu

### 2.3 TrackQueue Component (NEW)
**File**: `auralis-web/frontend/src/components/player/TrackQueue.tsx`

**Requirements from screenshot**:
- Shows at bottom of main content area
- Displays current queue/album tracks
- Numbered list (1, 2, 3, 4...)
- Track title and duration
- Current track highlighted
- Compact spacing (48px row height)

**Visual example from screenshot**:
```
1  Harmonic Light        4:10
2  Pulse of the Night    3:58
3  Electric Dreams       5:21  ← Current (highlighted)
4  Lucid Voyage          4:45
```

### 2.4 Enhanced Sidebar
**File**: `auralis-web/frontend/src/components/Sidebar.tsx` (update existing)

**Enhancements needed**:
- [ ] Add aurora gradient logo at top
- [ ] Implement active state with accent border-left (4px)
- [ ] Add smooth hover transitions
- [ ] Update icon sizes to 20x20px
- [ ] Improve spacing (40px item height)
- [ ] Add collapse/expand animation for playlists
- [ ] Create "Add Playlist" button with gradient accent

### 2.5 Enhanced BottomPlayerBar
**File**: `auralis-web/frontend/src/components/BottomPlayerBar.tsx` (update existing)

**Enhancements needed**:
- [ ] Aurora gradient play button (large, circular)
- [ ] Gradient progress bar
- [ ] Album art 60x60px with rounded corners
- [ ] Gradient volume slider
- [ ] Magic toggle with aurora accent when on
- [ ] Smooth animations on all controls
- [ ] Better layout spacing

---

## Phase 3: Enhanced Features (Week 3)

### 3.1 SearchBar Component
**File**: `auralis-web/frontend/src/components/SearchBar.tsx`

**Requirements**:
- Pill shape (border-radius: 24px)
- Height: 48px
- Semi-transparent background (#1a1f3a80)
- Search icon left side (20x20px)
- Placeholder: "Search" in gray
- Focus: Border glow with accent color
- Real-time search with debounce

### 3.2 EmptyState Component
**File**: `auralis-web/frontend/src/components/shared/EmptyState.tsx`

**Requirements**:
- Center-aligned content
- Large icon (64x64px) in accent color
- Primary text (20px): "No music yet"
- Secondary text (14px, gray): "Scan a folder to get started"
- Action button with gradient background

**Variants**:
- Empty library
- No search results
- No playlists
- No queue

### 3.3 ContextMenu Component
**File**: `auralis-web/frontend/src/components/shared/ContextMenu.tsx`

**Requirements**:
- Dark background with subtle shadow
- Hover highlights with accent color
- Menu items:
  - Play / Play Next / Add to Queue
  - Add to Playlist → (submenu)
  - Add to Favourites
  - Show Album / Artist
  - Properties / Info
- Smooth fade-in animation
- Click outside to close

### 3.4 Enhanced PresetPane
**File**: `auralis-web/frontend/src/components/PresetPane.tsx` (update existing)

**Enhancements needed**:
- [ ] Gradient toggle switch
- [ ] Custom styled dropdown (dark theme)
- [ ] Gradient slider for intensity
- [ ] Uppercase labels with letter-spacing
- [ ] Preset descriptions with icons
- [ ] Smooth expand/collapse animation

---

## Phase 4: Layout & Integration (Week 4)

### 4.1 Update Main Layout
**File**: `auralis-web/frontend/src/ComfortableApp.tsx`

**Tasks**:
- [ ] Integrate TrackQueue below album grid
- [ ] Add SearchBar to main content area header
- [ ] Implement proper scrolling (main area only)
- [ ] Add EmptyState when library is empty
- [ ] Integrate ContextMenu system
- [ ] Polish spacing and padding throughout

### 4.2 Grid View Enhancements
**File**: `auralis-web/frontend/src/components/CozyLibraryView.tsx`

**Tasks**:
- [ ] Use new AlbumCard component
- [ ] Implement responsive grid (3-4 columns)
- [ ] Add proper gap spacing (16-24px)
- [ ] Implement infinite scroll or pagination
- [ ] Add loading skeleton states
- [ ] Smooth animations on load

### 4.3 List View Implementation
**File**: `auralis-web/frontend/src/components/library/TrackListView.tsx` (new)

**Tasks**:
- [ ] Create compact list view using TrackRow
- [ ] Add column headers (sortable)
- [ ] Implement virtual scrolling for performance
- [ ] Add multi-select functionality
- [ ] Context menu on right-click

---

## Phase 5: Animations & Polish (Week 5)

### 5.1 Micro-interactions
**Tasks**:
- [ ] Add hover animations to all interactive elements
- [ ] Implement smooth transitions (0.3s ease)
- [ ] Add glow effects on focus/active states
- [ ] Create pulse animation for loading states
- [ ] Add shimmer effect to loading skeletons

### 5.2 Advanced Animations
**Tasks**:
- [ ] Page transition animations
- [ ] Playlist expand/collapse animation
- [ ] Track queue slide-in/out
- [ ] Context menu fade-in
- [ ] Toast notification slide-in

### 5.3 Loading States
**Tasks**:
- [ ] Create skeleton screens for all views
- [ ] Add progress indicators for long operations
- [ ] Implement optimistic UI updates
- [ ] Add loading shimmer effect

### 5.4 Responsive Design
**Tasks**:
- [ ] Test on various screen sizes
- [ ] Adjust grid columns responsively
- [ ] Make sidebar collapsible on mobile
- [ ] Optimize touch interactions
- [ ] Test on tablets

---

## Phase 6: Integration & Testing (Week 6)

### 6.1 API Integration
**Tasks**:
- [ ] Connect AlbumCard to real track data
- [ ] Implement real-time playback with backend
- [ ] Connect search to backend API
- [ ] Integrate library scanning
- [ ] Connect playlist management

### 6.2 State Management
**Tasks**:
- [ ] Set up proper state management (Context or Redux)
- [ ] Implement playback state management
- [ ] Manage queue state
- [ ] Handle library state updates
- [ ] WebSocket integration for real-time updates

### 6.3 Testing
**Tasks**:
- [ ] Component unit tests
- [ ] Integration tests for user flows
- [ ] Visual regression tests
- [ ] Performance testing
- [ ] Accessibility testing

---

## Component Dependency Tree

```
ComfortableApp
├── Sidebar (enhanced)
│   ├── AuroraLogo (new)
│   └── PlaylistSection (enhanced)
├── MainContent
│   ├── SearchBar (new)
│   ├── LibraryView
│   │   ├── AlbumCard (new) × many
│   │   └── TrackRow (new) × many
│   ├── TrackQueue (new)
│   └── EmptyState (new)
├── PresetPane (enhanced)
│   ├── GradientToggle (new)
│   └── GradientSlider (new)
└── BottomPlayerBar (enhanced)
    ├── GradientButton (new)
    └── GradientSlider (new)

Shared Components:
├── GlowCard (new)
├── LoadingSpinner (new)
├── Toast (new)
└── ContextMenu (new)
```

---

## Quick Start Guide

### Start with Phase 1:

1. **Create the theme system first**:
   ```bash
   mkdir -p auralis-web/frontend/src/theme
   mkdir -p auralis-web/frontend/src/styles
   mkdir -p auralis-web/frontend/src/components/shared
   ```

2. **Build foundation components**:
   - Start with `auralisTheme.ts`
   - Then `globalStyles.ts`
   - Then shared components (GradientButton, GradientSlider)

3. **Move to core components**:
   - Build AlbumCard (most important visual element)
   - Update BottomPlayerBar (most visible player control)
   - Enhance Sidebar (navigation foundation)

4. **Integrate gradually**:
   - Replace existing components one at a time
   - Test each component thoroughly
   - Keep old components as fallback during development

---

## Success Metrics

### Visual Quality:
- ✅ Matches screenshot aesthetic
- ✅ Aurora gradients throughout
- ✅ Smooth 60fps animations
- ✅ Consistent spacing and typography
- ✅ Neon accents properly integrated

### Functionality:
- ✅ All player controls working
- ✅ Library browsing smooth
- ✅ Search responsive
- ✅ Context menus functional
- ✅ Real-time updates via WebSocket

### Performance:
- ✅ <100ms interaction response
- ✅ Smooth scrolling on large libraries
- ✅ Efficient rendering (React.memo where needed)
- ✅ Optimized bundle size

### Accessibility:
- ✅ Keyboard navigation working
- ✅ Screen reader compatible
- ✅ Proper ARIA labels
- ✅ Focus indicators visible

---

## Resources

### Design References:
- Target screenshot (in conversation history)
- CLAUDE.md - UI/UX Design Philosophy section
- CLAUDE.md - Component Implementation Guidelines

### Technical Docs:
- Material-UI: https://mui.com/
- React: https://react.dev/
- TypeScript: https://www.typescriptlang.org/

### Inspiration:
- Spotify desktop app
- Apple Music / iTunes
- Rhythmbox
- Cider music player

---

**Last Updated**: 2025-10-15
**Status**: Ready to begin Phase 1
**Estimated Timeline**: 6 weeks for complete implementation
