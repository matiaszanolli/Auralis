# ComfortableApp Refactoring Plan

## Current State Analysis

**File**: `ComfortableApp.tsx`
**Current Lines**: 636 lines
**Issues**: Violates 300-line module size guideline, combines multiple responsibilities

### Current Responsibilities

1. **State Management** (15 state variables)
   - UI state: sidebar, drawer, preset pane, lyrics, settings
   - Playback state: currentTrack, isPlaying, playbackTime
   - View state: currentView, searchQuery, searchResultView
   - Config: useEnhancementPaneV2

2. **Keyboard Shortcuts** (lines 125-285)
   - 15+ keyboard shortcut definitions
   - Hook initialization with useKeyboardShortcuts
   - Help dialog state and handlers

3. **Drag & Drop Logic** (lines 318-414)
   - Complex handler with multiple conditions
   - Queue management
   - Playlist management
   - Reordering logic

4. **Layout Management** (lines 416-632)
   - Responsive breakpoints (mobile, tablet, desktop)
   - Desktop/mobile sidebar variations
   - Mobile drawer with swipe
   - Top bar with search
   - Content area layout
   - Right pane with enhancement controls
   - Bottom player bar

5. **Event Handlers** (lines 98-316)
   - Track playback
   - Enhancement toggles
   - Navigation
   - Settings management
   - Search result handling

6. **Responsive Behavior**
   - Auto-collapse sidebar on mobile
   - Hide enhancement pane on tablet
   - Mobile drawer vs desktop sidebar

---

## Proposed Architecture

### Refactored Structure (Target: <300 lines per component)

```
ComfortableApp.tsx (Main Container ~100 lines)
├── hooks/
│   ├── useAppLayout.ts (Responsive state)
│   ├── useAppKeyboardShortcuts.ts (Keyboard logic)
│   └── useAppDragDrop.ts (Drag & drop logic)
├── components/
│   ├── AppSidebar.tsx (Desktop + mobile sidebar)
│   ├── AppTopBar.tsx (Search, title, connection status)
│   ├── AppMainContent.tsx (Library view)
│   ├── AppEnhancementPane.tsx (Right pane with V2 toggle)
│   ├── AppContainer.tsx (Overall layout structure)
│   └── __tests__/
│       ├── AppSidebar.test.tsx
│       ├── AppTopBar.test.tsx
│       └── ...
└── services/
    └── dragDropHandlers.ts (Drag & drop utilities)
```

---

## Detailed Refactoring Steps

### Step 1: Extract Keyboard Shortcuts Logic → `useAppKeyboardShortcuts.ts`

**Location**: `hooks/useAppKeyboardShortcuts.ts`

**Responsibility**:
- Define keyboard shortcuts array
- Initialize useKeyboardShortcuts hook
- Manage help dialog state
- Return formatted shortcuts for use

**Extracted Code**:
```typescript
// Input: state setters and API methods
// Output: shortcuts, isHelpOpen, handlers

interface KeyboardShortcutsConfig {
  onPlayPause: () => void;
  onNextTrack: () => void;
  onPreviousTrack: () => void;
  onVolumeChange: (volume: number) => void;
  onViewChange: (view: string) => void;
  onSearchFocus: () => void;
  onSearchClear: () => void;
  onSettingsOpen: () => void;
}

export const useAppKeyboardShortcuts = (config: KeyboardShortcutsConfig) => {
  // ... keyboard setup logic ...
}
```

**Benefit**:
- Reduces ComfortableApp by ~160 lines
- Keyboard shortcuts become testable
- Easy to modify shortcuts without touching ComfortableApp
- Reusable in other components

---

### Step 2: Extract Drag & Drop Logic → `useAppDragDrop.ts`

**Location**: `hooks/useAppDragDrop.ts`

**Responsibility**:
- Handle drag end events
- Route to correct API endpoint
- Provide success/error feedback
- Abstract fetch calls

**Extracted Code**:
```typescript
export const useAppDragDrop = (info: ToastFunction, success: ToastFunction) => {
  const handleDragEnd = useCallback(async (result: DropResult) => {
    // ... existing drag drop logic ...
  }, [info, success]);

  return { handleDragEnd };
}
```

**Benefit**:
- Reduces ComfortableApp by ~100 lines
- Centralizes drag-drop logic for testing
- Can be reused in other components needing drag-drop

---

### Step 3: Extract Responsive Layout State → `useAppLayout.ts`

**Location**: `hooks/useAppLayout.ts`

**Responsibility**:
- Manage responsive breakpoints
- Handle sidebar collapse on mobile
- Track mobile drawer state
- Handle enhancement pane visibility

**Extracted Code**:
```typescript
interface LayoutState {
  isMobile: boolean;
  isTablet: boolean;
  sidebarCollapsed: boolean;
  mobileDrawerOpen: boolean;
  presetPaneCollapsed: boolean;
}

export const useAppLayout = (): LayoutState & LayoutActions => {
  // ... existing layout logic ...
}
```

**Benefit**:
- Reduces ComfortableApp by ~50 lines
- Makes responsive behavior testable
- Clear separation of layout concerns
- Easy to modify breakpoints

---

### Step 4: Create `AppTopBar.tsx` Component

**Location**: `components/AppTopBar.tsx`
**Size Target**: ~120 lines

**Responsibility**:
- Mobile hamburger menu
- Title display
- Connection status indicator
- Search bar integration

**Props**:
```typescript
interface AppTopBarProps {
  onMobileMenuToggle: () => void;
  mobileDrawerOpen: boolean;
  isMobile: boolean;
  isConnected: boolean;
  onSearchResultClick: (result: {type: string; id: number}) => void;
}
```

**Benefit**:
- Consolidates top bar logic
- Easier to test search integration
- Clean component boundaries

---

### Step 5: Create `AppSidebar.tsx` Component

**Location**: `components/AppSidebar.tsx`
**Size Target**: ~150 lines

**Responsibility**:
- Manage both desktop and mobile sidebar
- Handle navigation
- Settings button
- Collapse/expand toggle

**Props**:
```typescript
interface AppSidebarProps {
  isMobile: boolean;
  mobileDrawerOpen: boolean;
  sidebarCollapsed: boolean;
  onToggleCollapse: () => void;
  onNavigate: (view: string) => void;
  onOpenSettings: () => void;
  onCloseMobileDrawer?: () => void;
}
```

**Benefit**:
- Separates sidebar logic from main component
- Single source for sidebar behavior
- Responsive behavior contained

---

### Step 6: Create `AppMainContent.tsx` Component

**Location**: `components/AppMainContent.tsx`
**Size Target**: ~60 lines

**Responsibility**:
- Wrap CozyLibraryView
- Manage content area padding
- Handle track play callbacks

**Props**:
```typescript
interface AppMainContentProps {
  currentView: string;
  onTrackPlay: (track: Track) => void;
}
```

**Benefit**:
- Clean content area separation
- Easier to add features (playlists, queue view, etc.)
- Manageable component size

---

### Step 7: Create `AppEnhancementPane.tsx` Component

**Location**: `components/AppEnhancementPane.tsx`
**Size Target**: ~80 lines

**Responsibility**:
- Toggle between AutoMasteringPane and EnhancementPaneV2
- Handle collapse/expand
- Route mastering events

**Props**:
```typescript
interface AppEnhancementPaneProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onMasteringToggle: (enabled: boolean) => void;
  useEnhancementPaneV2: boolean;
  isTablet: boolean;
}
```

**Benefit**:
- Encapsulates pane toggle logic
- Easy to add new pane variants
- Clear feature flag integration

---

### Step 8: Refactor `ComfortableApp.tsx` (New ~150 lines)

**New Structure**:
```typescript
function ComfortableApp() {
  // 1. Layout state (responsive, UI state)
  const layout = useAppLayout();

  // 2. API & context
  const { isConnected } = useWebSocketContext();
  const { success, info } = useToast();
  const playerAPI = usePlayerAPI();

  // 3. Local state (only essentials)
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [currentView, setCurrentView] = useState('songs');
  const [searchQuery, setSearchQuery] = useState('');
  const [useEnhancementPaneV2, setUseEnhancementPaneV2] = useState(...);

  // 4. Event handlers
  const handleTrackPlay = (track: Track) => { ... };
  const handleNavigate = (view: string) => { ... };

  // 5. Hooks for complex logic
  const { handleDragEnd } = useAppDragDrop(info, success);
  const { isHelpOpen, closeHelp, ... } = useAppKeyboardShortcuts({...});

  // 6. Render layout with extracted components
  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <AppContainer>
        <AppSidebar {...} />
        <Box>
          <AppTopBar {...} />
          <AppMainContent {...} />
        </Box>
        <AppEnhancementPane {...} />
      </AppContainer>
      <PlayerBarV2Connected />
    </DragDropContext>
  );
}
```

**Benefit**:
- Follows 300-line guideline
- Clear component composition
- Easy to understand flow
- Each piece is independently testable

---

## Implementation Order

### Phase 1: Create Hooks (Low Risk)
1. `useAppLayout.ts` - Responsive behavior
2. `useAppKeyboardShortcuts.ts` - Keyboard logic
3. `useAppDragDrop.ts` - Drag & drop

**Why First**:
- No changes to JSX
- Easier to test independently
- Can run existing tests in parallel

### Phase 2: Create Wrapper Component
4. `AppContainer.tsx` - Main layout container

**Why Second**:
- Sets up structure for child components
- Minimal logic, mostly layout

### Phase 3: Create Feature Components (Medium Risk)
5. `AppSidebar.tsx` - Navigation
6. `AppTopBar.tsx` - Search & title
7. `AppMainContent.tsx` - Content area
8. `AppEnhancementPane.tsx` - Right pane

**Why Third**:
- Building on established patterns
- Each can be tested in isolation
- Less dependent on other new components

### Phase 4: Refactor Main Component (High Risk)
9. Refactor `ComfortableApp.tsx` to use new components

**Why Last**:
- All dependencies already extracted
- Can incrementally replace sections
- Easy to verify with existing tests

---

## Testing Strategy

### 1. Test New Hooks
```typescript
// hooks/__tests__/useAppLayout.test.ts
describe('useAppLayout', () => {
  it('collapses sidebar on mobile', () => { ... });
  it('hides enhancement pane on tablet', () => { ... });
});

// hooks/__tests__/useAppKeyboardShortcuts.test.ts
describe('useAppKeyboardShortcuts', () => {
  it('handles play/pause shortcut', () => { ... });
  it('opens help on ?', () => { ... });
});

// hooks/__tests__/useAppDragDrop.test.ts
describe('useAppDragDrop', () => {
  it('adds track to queue on drop', async () => { ... });
  it('shows error on failed API call', async () => { ... });
});
```

### 2. Test New Components
```typescript
// components/__tests__/AppTopBar.test.tsx
describe('AppTopBar', () => {
  it('renders mobile menu on mobile', () => { ... });
  it('shows connection status', () => { ... });
});

// components/__tests__/AppSidebar.test.tsx
describe('AppSidebar', () => {
  it('handles navigation clicks', () => { ... });
  it('toggles collapse state', () => { ... });
});
```

### 3. Integration Testing
- Test ComfortableApp with all new components
- Verify responsive behavior
- Test keyboard shortcuts end-to-end
- Test drag-drop integration

### 4. Regression Testing
- Run existing tests to ensure no breaking changes
- Test all navigation flows
- Test all settings dialogs
- Test player bar integration

---

## File Size Comparison

### Before Refactoring
- `ComfortableApp.tsx`: 636 lines (❌ Violates 300-line limit)

### After Refactoring
- `ComfortableApp.tsx`: ~150 lines ✅
- `AppContainer.tsx`: ~100 lines ✅
- `AppSidebar.tsx`: ~150 lines ✅
- `AppTopBar.tsx`: ~120 lines ✅
- `AppMainContent.tsx`: ~60 lines ✅
- `AppEnhancementPane.tsx`: ~80 lines ✅
- `useAppLayout.ts`: ~50 lines ✅
- `useAppKeyboardShortcuts.ts`: ~160 lines ✅
- `useAppDragDrop.ts`: ~100 lines ✅

**Total New Code**: ~970 lines (distributed across 9 files)
**Improvement**: All files under 300-line limit, better separation of concerns

---

## Risk Mitigation

### 1. Backward Compatibility
- ✅ No breaking changes to child components
- ✅ No changes to external APIs
- ✅ All existing props/state forwarded correctly

### 2. Testing Coverage
- ✅ Unit test each new hook
- ✅ Unit test each new component
- ✅ Integration test full flow
- ✅ Run existing test suite to verify no regressions

### 3. Incremental Rollout
- ✅ Can refactor one section at a time
- ✅ Each component can be tested independently
- ✅ Easy to revert if issues found

### 4. Code Review Checkpoints
- After hooks extraction
- After component creation
- Before final ComfortableApp refactoring

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Main file size | 636 lines | ~150 lines |
| Max component size | 636 lines (❌) | 150 lines ✅ |
| Keyboard shortcuts testability | Hard | Easy |
| Drag-drop testability | Hard | Easy |
| Responsive logic testability | Hard | Easy |
| Component reusability | Low | High |
| Maintenance burden | High | Low |
| Code readability | Poor | Good |

---

## Dependencies & Imports

### New Hook Dependencies
- `react` (useState, useEffect, useCallback, useMediaQuery, useTheme)
- `@mui/material` (useMediaQuery, useTheme)
- `./contexts/WebSocketContext` (useWebSocketContext)
- `./components/shared/Toast` (useToast)
- `./hooks/useKeyboardShortcuts` (useKeyboardShortcuts)
- `./hooks/usePlayerAPI` (usePlayerAPI)

### New Component Dependencies
- `react`
- `@mui/material` (Box, Typography, IconButton, SwipeableDrawer)
- `@mui/icons-material`
- `./components/*` (existing child components)
- `./hooks/*` (new custom hooks)

---

## Next Steps

1. **Review this plan** with the team
2. **Approve refactoring approach**
3. **Execute Phase 1** (hooks extraction)
4. **Execute Phase 2** (wrapper components)
5. **Execute Phase 3** (feature components)
6. **Execute Phase 4** (main component refactoring)
7. **Run full test suite** and verify
8. **Deploy** and monitor for issues

---

## Questions & Considerations

1. **Should we keep both AutoMasteringPane and EnhancementPaneV2?**
   - Current answer: Yes (via feature flag)
   - Future: Remove AutoMasteringPane once V2 is stable

2. **Should we extract more state?**
   - Current answer: No, only responsive/UI essentials in hooks
   - Logic-heavy operations already delegated to dedicated hooks

3. **Should we add state management (Redux, Zustand)?**
   - Current answer: Not yet, current approach is sufficient
   - Consider if state grows beyond 20+ variables

4. **Should we memoize components?**
   - Answer: Yes, use React.memo on extracted components
   - Optimize prop drilling with useCallback

---

## Estimated Effort

- **Planning & Design**: 2 hours ✅ (done)
- **Hook Implementation**: 4-6 hours
- **Component Implementation**: 6-8 hours
- **Testing & Refactoring**: 4-6 hours
- **Documentation & Code Review**: 2-3 hours
- **Total Estimated**: 18-25 hours

---

## Success Criteria

- ✅ All files under 300-line limit
- ✅ All tests passing (existing + new)
- ✅ No breaking changes to existing functionality
- ✅ Improved code readability
- ✅ Better separation of concerns
- ✅ Easier to test individual features
- ✅ Easier to modify/extend features
