# Component Architecture Reorganization Guide

**Document Type**: Architecture Plan
**Status**: Ready for Implementation
**Complexity**: High (multi-phase refactoring)
**Estimated Effort**: 4 weeks (can be parallelized)
**Priority**: Medium-High (prevents technical debt)

---

## Executive Summary

The current component architecture (97 .tsx files across 16 directories) has organizational issues that make the codebase harder to navigate and maintain:

- **8 components scattered at root level** (unclear hierarchy)
- **"v2" naming conflicts** (player-bar-v2, enhancement-pane-v2)
- **Mixed concerns** (library/ has 30+ files with unclear subdivisions)
- **Missing feature grouping** (discovery features scattered)

This guide proposes a **feature-based + layered architecture** that organizes components by:
1. **Core responsibility** (core/, layouts/, features/, shared/, debug/)
2. **Feature domains** (library/, player/, enhancement/, discovery/)
3. **Shared concerns** (UI, feedback, animations)

**Expected Benefits:**
- 🎯 **Clarity**: Easy to find where code lives
- 📈 **Scalability**: Easy to add new features
- 🔧 **Maintainability**: Related code grouped together
- 🧪 **Testing**: Features can be tested independently
- 👥 **Onboarding**: Faster for new developers
- ♻️ **Refactoring**: Easier within feature boundaries

---

## Current State Analysis

### Component Distribution
```
Total Components:    97 .tsx files
Root Level Files:    8 (should be moved)
Max Directory Size:  library/ with 30+ files (mixed concerns)
Versions:           v2 suffixes on player-bar and enhancement-pane
Test Coverage:      ~50% of components have tests
```

### Problem Areas

#### 1. Scattered Root-Level Components (8 files)
**Current**: Components at `components/CozyLibraryView.tsx`, `components/SimilarTracks.tsx`, etc.
**Problem**: Hard to navigate, unclear hierarchy
**Examples**:
- `CozyLibraryView.tsx` - Library feature (belongs in `features/library/`)
- `SimilarTracks.tsx` - Discovery feature (belongs in `features/discovery/`)
- `RadialPresetSelector.tsx` - Enhancement UI (belongs in `features/enhancement/`)
- `Sidebar.tsx` - Layout component (belongs in `layouts/`)

#### 2. Duplicate/Conflicting Structures
**Current**: `player/` vs `player-bar-v2/`, `enhancement-pane-v2/`
**Problem**: Unclear which version is active
**Impact**: Confusion about where to import from

#### 3. Mixed Concerns in Directories
**Current**: `library/` has 30+ files mixing:
- Views (LibraryView.tsx, AlbumDetailView.tsx)
- Controls (BatchActionsToolbar.tsx, LibraryHeader.tsx)
- Items (TrackRow.tsx, AlbumCard.tsx)
- Searches (GlobalSearch.tsx, SearchInput.tsx)

**Problem**: Hard to understand what each piece does
**Impact**: Slow to navigate, easy to put new code in wrong place

#### 4. Missing Feature Grouping
**Current**: Discovery features are scattered
- `SimilarTracks.tsx` at root
- `SimilarityVisualization.tsx` at root
- No clear home for discovery features

---

## Proposed Architecture

### Architectural Principles

#### 1. **Feature-Based Organization**
- Group components by **feature/domain first**
- Not by component type
- Each feature is self-contained

#### 2. **Clear Layering**
```
core/       → App structure only (App.tsx, AppRoutes.tsx)
layouts/    → App layout wrappers (Sidebar, TopBar, PlayerBar)
features/   → Feature modules (library, player, enhancement, etc)
shared/     → Reusable components (UI, feedback, animations)
debug/      → Dev/debug only (DebugInfo, DevTools)
```

#### 3. **No "v2" or Legacy Versions**
- Consolidate active versions
- Remove old versions
- Use git history for legacy reference

#### 4. **Consistent Naming**
- Features: plural (`library/`, `player/`, `enhancement/`)
- Shared UI: categorized (`shared/ui/buttons/`, `shared/ui/inputs/`)
- Clear intent in naming

#### 5. **Self-Contained Features**
- Each feature in `features/` is independently understandable
- Clear dependencies documented
- Can be toggled/disabled as a unit

### Target Architecture

```
components/
├── core/                              # App structure (1-2 files)
│   ├── App.tsx                        # Main app component
│   ├── AppContainer.tsx               # Container/orchestration
│   └── AppRoutes.tsx                  # Route definitions
│
├── layouts/                           # Layout components (5-7 files)
│   ├── MainLayout.tsx                 # Main app layout
│   ├── Sidebar.tsx                    # ✅ MOVE FROM ROOT
│   ├── TopBar.tsx
│   ├── EnhancementPane.tsx
│   ├── PlayerBar.tsx                  # ✅ CONSOLIDATE FROM player-bar-v2/
│   └── __tests__/
│
├── features/                          # Feature modules (85+ files organized)
│   │
│   ├── library/                       # 📚 Library browsing (~30 files)
│   │   ├── LibraryView.tsx            # ✅ MOVE FROM root CozyLibraryView.tsx
│   │   ├── __tests__/
│   │   │
│   │   ├── LibrarySearch/             # Search functionality
│   │   │   ├── GlobalSearch.tsx       # Main search component
│   │   │   ├── SearchInput.tsx        # Input component
│   │   │   ├── SearchResults/         # Results display
│   │   │   │   ├── ResultsContainer.tsx
│   │   │   │   ├── ResultGroup.tsx
│   │   │   │   ├── ResultAvatar.tsx
│   │   │   │   └── __tests__/
│   │   │   └── __tests__/
│   │   │
│   │   ├── LibraryViews/              # Main library views
│   │   │   ├── AlbumsTab.tsx
│   │   │   ├── ArtistsTab.tsx
│   │   │   ├── TracksTab.tsx
│   │   │   ├── GridView.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── DetailViews/               # Detail view pages
│   │   │   ├── AlbumDetailView.tsx
│   │   │   ├── ArtistDetailView.tsx
│   │   │   ├── ArtistHeader.tsx
│   │   │   ├── AlbumTrackTable.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── Items/                     # List items/cards
│   │   │   ├── TrackRow.tsx
│   │   │   ├── DraggableTrackRow.tsx
│   │   │   ├── AlbumCard.tsx
│   │   │   ├── ArtistListItem.tsx
│   │   │   └── __tests__/
│   │   │
│   │   └── Controls/                  # Library controls
│   │       ├── BatchActionsToolbar.tsx
│   │       ├── LibraryHeader.tsx
│   │       ├── ViewToggle.tsx
│   │       └── __tests__/
│   │
│   ├── player/                        # 🎵 Playback & control (~10 files)
│   │   ├── PlayerBar.tsx              # Main player bar (or in layouts/)
│   │   ├── PlayerControls.tsx         # Play/pause/next/prev
│   │   ├── ProgressBar.tsx
│   │   ├── VolumeControl.tsx
│   │   ├── DurationDisplay.tsx
│   │   ├── QueuePanel.tsx
│   │   ├── LyricsPanel.tsx
│   │   ├── PlayPauseButton.tsx
│   │   └── __tests__/
│   │
│   ├── enhancement/                   # ✨ Audio enhancement (~10 files)
│   │   ├── EnhancementPanel.tsx
│   │   ├── EnhancementToggle.tsx      # ✅ MOVE FROM root
│   │   ├── __tests__/
│   │   │
│   │   ├── Controls/                  # Enhancement controls
│   │   │   ├── ParameterBar.tsx
│   │   │   ├── ProcessingParameters.tsx
│   │   │   ├── ParameterChip.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── Info/                      # Enhancement info display
│   │   │   ├── AudioCharacteristics.tsx
│   │   │   ├── InfoBox.tsx
│   │   │   ├── LoadingState.tsx
│   │   │   └── __tests__/
│   │   │
│   │   └── Presets/                   # Preset selection
│   │       ├── RadialPresetSelector.tsx # ✅ MOVE FROM root
│   │       └── __tests__/
│   │
│   ├── discovery/                     # 🔍 Music discovery (5+ files, NEW)
│   │   ├── SimilarTracks.tsx          # ✅ MOVE FROM root
│   │   ├── SimilarityVisualization.tsx # ✅ MOVE FROM root
│   │   ├── SimilarTracksViewer.tsx
│   │   ├── Recommendations.tsx
│   │   └── __tests__/
│   │
│   ├── settings/                      # ⚙️ Settings & config (~8 files)
│   │   ├── SettingsDialog.tsx
│   │   ├── __tests__/
│   │   │
│   │   ├── Panels/                    # Settings panels
│   │   │   ├── AudioSettingsPanel.tsx
│   │   │   ├── PlaybackSettingsPanel.tsx
│   │   │   ├── InterfaceSettingsPanel.tsx
│   │   │   ├── LibrarySettingsPanel.tsx
│   │   │   ├── EnhancementSettingsPanel.tsx
│   │   │   ├── AdvancedSettingsPanel.tsx
│   │   │   └── __tests__/
│   │   │
│   │   └── Navigation/
│   │       ├── SettingsTabNav.tsx
│   │       └── __tests__/
│   │
│   └── playlist/                      # 📋 Playlist management (3-5 files)
│       ├── PlaylistManager.tsx
│       ├── PlaylistItems.tsx
│       ├── PlaylistActions.tsx
│       └── __tests__/
│
├── shared/                            # Shared/reusable (~30 files)
│   │
│   ├── ui/                            # Pure UI components
│   │   │
│   │   ├── buttons/                   # Button components
│   │   │   ├── Button.tsx
│   │   │   ├── IconButton.tsx
│   │   │   ├── PlayButton.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── inputs/                    # Input components
│   │   │   ├── TextInput.tsx
│   │   │   ├── SearchInput.tsx
│   │   │   ├── NumberInput.tsx
│   │   │   ├── Select.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── dialogs/                   # Dialog/modal components
│   │   │   ├── Dialog.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── EditMetadataDialog.tsx # ✅ MOVE FROM library/
│   │   │   └── __tests__/
│   │   │
│   │   ├── cards/                     # Card components
│   │   │   ├── Card.tsx
│   │   │   ├── CardList.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── lists/                     # List components
│   │   │   ├── VirtualList.tsx
│   │   │   ├── InfiniteScroll.tsx
│   │   │   ├── InfiniteScrollTrigger.tsx
│   │   │   ├── EndOfListIndicator.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── media/                     # Media components
│   │   │   ├── AlbumArt.tsx
│   │   │   ├── Avatar.tsx
│   │   │   ├── Thumbnail.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── bars/                      # Bar/slider components
│   │   │   ├── ProgressBar.tsx
│   │   │   ├── Slider.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── loaders/                   # Loading components
│   │   │   ├── Skeleton.tsx
│   │   │   ├── Spinner.tsx
│   │   │   ├── LoadingIndicator.tsx
│   │   │   ├── GridLoadingState.tsx
│   │   │   └── __tests__/
│   │   │
│   │   ├── badges/                    # Badge components
│   │   │   ├── Badge.tsx
│   │   │   └── __tests__/
│   │   │
│   │   └── tooltips/                  # Tooltip components
│   │       ├── Tooltip.tsx
│   │       └── __tests__/
│   │
│   ├── feedback/                      # User feedback components
│   │   ├── Toast.tsx
│   │   ├── ProcessingToast.tsx        # ✅ MOVE FROM root
│   │   ├── Notification.tsx
│   │   ├── ErrorBoundary.tsx
│   │   └── __tests__/
│   │
│   └── animations/                    # Animation/transition components
│       ├── transitions/               # ✅ MOVE/CONSOLIDATE
│       └── __tests__/
│
├── debug/                             # Development/debug (dev only)
│   ├── DebugInfo.tsx                  # ✅ MOVE FROM root
│   ├── DevTools.tsx
│   └── __tests__/
│
└── index.ts                           # Barrel export (if needed)
```

---

## Migration Strategy

### Phase 1: Foundation (Days 1-5)

**Goals**: Create new structure, move structural components

**Tasks**:
1. Create new directories:
   - `components/core/`
   - `components/layouts/`
   - `components/features/{library,player,enhancement,discovery,settings,playlist}/`
   - `components/shared/{ui/*,feedback,animations}/`
   - `components/debug/`

2. Create `.gitkeep` files in subdirectories

3. Move app-level components:
   - `app-layout/*` → `core/` + `layouts/`
   - `navigation/*` → relevant feature directories
   - `transitions/` → `shared/animations/`

4. Create barrel exports (index.ts) for each directory

**Commits**:
- `refactor: create new component architecture structure`
- `refactor: move core and layout components`

### Phase 2: Features (Days 6-15)

**Goals**: Reorganize features into domains

**Tasks by Feature**:

**Library (Days 6-8)**:
1. Create subdirectories in `features/library/`:
   - `LibrarySearch/`, `LibraryViews/`, `DetailViews/`, `Items/`, `Controls/`
2. Move files from `library/` into appropriate subdirectories
3. Update imports
4. Move `CozyLibraryView.tsx` → `features/library/LibraryView.tsx`
5. Run tests, fix breakage

**Player (Days 9-10)**:
1. Consolidate `player/` and `player-bar-v2/`
2. Create `features/player/` with all player components
3. Create `layouts/PlayerBar.tsx` for main player bar
4. Update imports
5. Remove `player-bar-v2/` directory
6. Run tests

**Enhancement (Days 11-12)**:
1. Move `enhancement-pane-v2/` → `features/enhancement/`
2. Remove "v2" from directory and files
3. Create subdirectories: `Controls/`, `Info/`, `Presets/`
4. Move `RadialPresetSelector.tsx` from root
5. Update imports

**Discovery (Days 13-14)**:
1. Create new `features/discovery/` directory
2. Move `SimilarTracks.tsx` from root
3. Move `SimilarityVisualization.tsx` from root
4. Create supporting structure
5. Add documentation

**Settings (Days 15)**:
1. Reorganize `settings/` with subdirectories: `Panels/`, `Navigation/`
2. Move panel components into `Panels/`
3. Update imports

**Commits** (one per feature):
- `refactor: reorganize library feature components`
- `refactor: consolidate player components`
- `refactor: reorganize enhancement feature`
- `refactor: create discovery feature module`
- `refactor: organize settings components`

### Phase 3: Shared Components (Days 16-19)

**Goals**: Create shared component library

**Tasks**:
1. Create `shared/ui/` subdirectories for each component type
2. Move generic UI components into appropriate subdirectories
3. Move `ProcessingToast.tsx` → `shared/feedback/`
4. Move `EditMetadataDialog.tsx` → `shared/ui/dialogs/`
5. Consolidate duplicate components
6. Create barrel exports

**Commits**:
- `refactor: organize shared UI components`
- `refactor: reorganize feedback components`

### Phase 4: Imports & Validation (Days 20-21)

**Goals**: Fix all imports, ensure clean build

**Tasks**:
1. Use find/replace to update all component imports
2. Update path aliases in TypeScript config (ensure `@/components/*` works)
3. Run build: `npm run build`
4. Run tests: `npm run test:memory`
5. Fix any broken imports (usually from tests)
6. Update barrel exports
7. Verify hot reload works

**Commands**:
```bash
# Update imports (use IDE find/replace or script)
find . -name "*.tsx" -o -name "*.ts" | xargs sed -i 's|from.*components/|from @/components/|g'

# Build
npm run build

# Test
npm run test:memory

# Type check
npx tsc --noEmit
```

**Commits**:
- `refactor: update all component imports`
- `refactor: move debug components`

---

## File Movement Summary

### Root Level → Features (8 files)
```
CozyLibraryView.tsx              → features/library/LibraryView.tsx
SimilarTracks.tsx                → features/discovery/SimilarTracks.tsx
SimilarityVisualization.tsx       → features/discovery/SimilarityVisualization.tsx
RadialPresetSelector.tsx          → features/enhancement/Presets/RadialPresetSelector.tsx
Sidebar.tsx                       → layouts/Sidebar.tsx
ThemeToggle.tsx                   → (check current location)
```

### Nested Consolidation
```
player-bar-v2/                   → Consolidate into features/player/ + layouts/PlayerBar.tsx
enhancement-pane-v2/             → features/enhancement/ (remove v2)
album/                           → library/Items/ or features/library/
track/                           → library/Items/ or features/discovery/
modals/                          → shared/ui/dialogs/
player/                          → features/player/ (consolidate with player-bar-v2)
```

---

## Testing Strategy

### Before Each Phase
```bash
# Verify build works
npm run build

# Run all tests
npm run test:memory

# Type check
npx tsc --noEmit
```

### During Phase
- Move files using `git mv` to preserve history
- Update imports as you go (small commits are better)
- Fix test imports immediately

### After Phase
- Run full test suite
- Verify no console errors
- Test hot reload (save a file and check browser)
- Verify production build works

---

## Import Path Updates

### Before
```typescript
import { CozyLibraryView } from '@/components/CozyLibraryView'
import { SimilarTracks } from '@/components/SimilarTracks'
import { RadialPresetSelector } from '@/components/RadialPresetSelector'
import { Sidebar } from '@/components/Sidebar'
```

### After
```typescript
import { LibraryView } from '@/components/features/library'
import { SimilarTracks } from '@/components/features/discovery'
import { RadialPresetSelector } from '@/components/features/enhancement/Presets'
import { Sidebar } from '@/components/layouts'
```

### Barrel Exports (index.ts)
```typescript
// components/features/library/index.ts
export { LibraryView } from './LibraryView'
export { GlobalSearch } from './LibrarySearch/GlobalSearch'
export { AlbumDetailView } from './DetailViews/AlbumDetailView'
// ... etc
```

---

## Validation Checklist

### After Each Phase
- [ ] All files moved with `git mv` (preserves history)
- [ ] All imports updated
- [ ] No broken imports (IDE shows no errors)
- [ ] Build succeeds: `npm run build`
- [ ] Tests pass: `npm run test:memory`
- [ ] No TypeScript errors: `npx tsc --noEmit`
- [ ] Hot reload works (save a file, check browser)
- [ ] No console errors in dev tools

### Final Validation (After Phase 4)
- [ ] Full test suite passes
- [ ] Production build works
- [ ] No circular dependencies
- [ ] All components properly exported
- [ ] Documentation updated
- [ ] CLAUDE.md updated with new architecture

---

## Documentation Updates

### 1. Create COMPONENT_ARCHITECTURE.md
Location: `docs/guides/COMPONENT_ARCHITECTURE.md`

Content:
- New architecture diagram
- How to add new components
- Import patterns
- Common locations by feature
- Do's and don'ts

### 2. Update CLAUDE.md
Add section: "Frontend Component Architecture"
- Point to COMPONENT_ARCHITECTURE.md
- Quick reference for component locations

### 3. Update Frontend README
- Document new structure
- Link to architecture guide

---

## Risk Mitigation

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Import cycle errors | Use barrel exports, maintain clean dependency graph |
| Tests break | Run full test suite after each phase, fix immediately |
| Hot reload stops working | Verify vite.config.ts paths, check barrel exports |
| Missing files after move | Use git mv, double-check all moves |
| Unclear location for new component | Document conventions in COMPONENT_ARCHITECTURE.md |

### Rollback Plan
If critical issues occur:
1. Commit current state with issue description
2. Identify phase causing issue
3. Revert that phase (git revert)
4. Fix issue in separate branch
5. Re-apply after fix

---

## Benefits of New Architecture

### Immediate Benefits
✅ **Clarity**: 97 components now organized logically
✅ **Discoverability**: Know where to find/add components
✅ **Navigation**: Easier to browse codebase

### Long-Term Benefits
✅ **Scalability**: Easy to add new features
✅ **Maintainability**: Related code grouped together
✅ **Testing**: Features can be tested independently
✅ **Refactoring**: Clear boundaries for changes
✅ **Onboarding**: New developers learn structure faster
✅ **Dependencies**: Clear feature dependencies visible

---

## Success Criteria

### Phase Completion
- ✅ All files moved for that phase
- ✅ All imports updated and working
- ✅ Build succeeds
- ✅ Tests pass
- ✅ No console errors

### Project Completion
- ✅ All 97 components organized
- ✅ Root directory clean (0 loose .tsx files)
- ✅ Clear feature boundaries
- ✅ Full test suite passes
- ✅ Production build works
- ✅ Architecture documented

---

**Last Updated**: November 23, 2025
**Status**: Ready for Implementation
**Estimated Total Time**: 3-4 weeks
**Difficulty**: High (but very structured)
