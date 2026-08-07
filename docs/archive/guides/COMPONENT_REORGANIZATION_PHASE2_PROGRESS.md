# Component Architecture Reorganization - Phase 2 In Progress

**Status**: Phase 2 (Feature Deep Reorganization) - IN PROGRESS
**Date Started**: November 23, 2025
**Commits**: 0fbe1ce (ContextMenu refactoring)

## Overview

Phase 2 focuses on breaking down oversized components and reorganizing library subdirectories. This phase is more surgical than Phase 1, addressing specific architectural issues.

## Completed Tasks

### ✅ ContextMenu Refactoring (485 lines → modular)

Successfully refactored the largest shared component:

**Before**:
- Single 485-line ContextMenu.tsx file
- Mixed concerns: state, UI, actions, styling, playlist integration

**After**:
- `ContextMenu/ContextMenu.tsx` (165 lines) - Main component
- `ContextMenu/useContextMenu.ts` (40 lines) - State hook
- `ContextMenu/contextMenuActions.ts` (189 lines) - Action generators
- `ContextMenu/PlaylistSection.tsx` (89 lines) - Playlist UI subcomponent
- `ContextMenu/index.ts` - Barrel export

**Reduction**: 485 lines → 165 lines (66% reduction in main component)

**Files Updated**:
- All imports already compatible via barrel export
- No breaking changes required
- `ContextMenu.old.tsx` kept as backup

## In Progress Tasks

### 🔄 AlbumCard Refactoring (365 lines)

Identified structure for breakdown:

```
AlbumCard/
├── AlbumCard.tsx (main, ~120 lines)
├── ArtworkSection/
│   ├── ArtworkContainer.tsx (~80 lines)
│   ├── PlayOverlay.tsx (~30 lines)
│   ├── LoadingOverlay.tsx (~20 lines)
│   └── NoArtworkButtons.tsx (~40 lines)
├── ArtworkMenu.tsx (~50 lines)
├── useArtworkHandlers.ts (~30 lines)
└── index.ts
```

**Key Components**:
1. **PlayOverlay** - Play button that appears on hover
2. **LoadingOverlay** - Circular progress during download/extract
3. **NoArtworkButtons** - Download and extract buttons for missing artwork
4. **ArtworkMenu** - More options menu for artwork management
5. **useArtworkHandlers** - Custom hook for artwork operations

**Benefits**:
- Separation of concerns (overlay rendering, menu handling)
- Reusable PlayOverlay component for other media types
- Easier testing of individual features
- Main component reduced to ~120 lines

### 🔄 EditMetadataDialog Refactoring (348 lines)

Identified structure for breakdown:

```
EditMetadataDialog/
├── EditMetadataDialog.tsx (main, ~100 lines)
├── FormFields/
│   ├── BasicFields.tsx (~60 lines)  [Title, Artist, Album, Genre fields]
│   ├── DateFields.tsx (~40 lines)   [Release date, recording date fields]
│   └── TagsField.tsx (~30 lines)    [Custom tags/keywords field]
├── DialogActions.tsx (~30 lines)    [Cancel/Save buttons]
├── useMetadataForm.ts (~40 lines)   [Form state and validation]
└── index.ts
```

**Key Subcomponents**:
1. **BasicFields** - Standard metadata (title, artist, album)
2. **DateFields** - Date-specific metadata
3. **TagsField** - Custom tags/keywords
4. **DialogActions** - Dialog footer with buttons
5. **useMetadataForm** - Form logic and validation

**Benefits**:
- Main component reduced to ~100 lines
- Reusable field components for other dialogs
- Centralized form validation logic
- Better organization of related fields

## Pending Tasks

### 📋 Library Subdirectory Reorganization

**Current structure** (30+ mixed files in library/):
```
library/
├── Views/                    # Tab views (albums, artists, tracks)
│   ├── AlbumsTab.tsx
│   ├── ArtistsTab.tsx
│   ├── TracksTab.tsx
│   └── ...
├── Search/                   # Search functionality
│   ├── GlobalSearch.tsx
│   ├── SearchInput.tsx
│   ├── SearchResults/
│   └── ...
├── Items/                    # Reusable list items
│   ├── TrackRow.tsx
│   ├── AlbumCard.tsx
│   ├── ArtistListItem.tsx
│   └── DraggableTrackRow.tsx
├── Details/                  # Detail views
│   ├── AlbumDetailView.tsx
│   ├── ArtistDetailView.tsx
│   └── ...
├── Controls/                 # Library controls
│   ├── BatchActionsToolbar.tsx
│   ├── LibraryHeader.tsx
│   ├── ViewToggle.tsx
│   └── ...
```

**Expected cleanup**:
- Clear subdirectory structure
- ~6-8 main subdirectories vs. current flat structure
- Easier navigation for library-related components
- Clear separation of concerns

### 🎨 Shared UI Subdirectory Organization

**Current structure** (empty subdirectories):
```
shared/ui/
├── buttons/        (empty)
├── inputs/         (empty)
├── dialogs/        (empty)
├── cards/          (empty)
├── lists/          (empty)
├── media/          (empty)
├── bars/           (empty)
├── loaders/        (empty)
├── badges/         (empty)
└── tooltips/       (empty)
```

**Action**: Populate with existing components
- Audit existing UI components
- Move to appropriate subdirectories
- Create shared base components where needed
- Update imports

### 🔄 Consolidate Duplicate AlbumArt Components

**Duplicates found**:
- `/album/AlbumArt.tsx`
- `/shared/AlbumArtDisplay.tsx`

**Action**:
- Audit both implementations
- Keep better/more feature-complete version
- Remove duplicate
- Update all imports

## Phase 2 Roadmap

### Week 1-2 (Current)
- ✅ ContextMenu refactoring complete
- 🔄 AlbumCard refactoring in progress
- 🔄 EditMetadataDialog refactoring in progress
- 📋 Library reorganization starting

### Week 3-4
- AlbumCard & EditMetadataDialog completion
- Library subdirectories reorganized
- Shared UI components organized
- Duplicate consolidation

### Week 5 (Finalization)
- All import paths updated
- Tests run and validated
- Build verification
- Phase 2 completion documentation

## Metrics & Impact

### Completed
- **Components broken down**: 1 (ContextMenu)
- **Lines reduced**: 320 lines (485 → 165)
- **Subcomponents created**: 4

### Planned
- **Components to refactor**: 2 (AlbumCard, EditMetadataDialog)
- **Expected lines saved**: ~400-450 lines total
- **Subcomponents to create**: ~15-18

### Structure Improvements
- **Library organization**: 1 flat directory → 6-8 organized subdirectories
- **Shared UI organization**: 10 empty → populated with components
- **Duplicate components eliminated**: 2 AlbumArt → 1

## Technical Details

### Refactoring Pattern Established

1. **Identify concerns** in oversized component
2. **Extract focused subcomponents** for each concern
3. **Create custom hooks** for stateful logic
4. **Create barrel exports** for clean imports
5. **Keep backward compatibility** via index.ts
6. **Preserve file history** with .old.tsx backup

### Import Compatibility

All refactored components maintain backward compatibility:
```typescript
// Old imports still work
import { ContextMenu, useContextMenu } from '@/components/shared/ContextMenu'

// New subcomponents available
import { PlaylistSection } from '@/components/shared/ContextMenu'
```

## Known Challenges

1. **Deep Dependencies**: AlbumCard and EditMetadataDialog have complex internal dependencies
2. **Form Management**: EditMetadataDialog has validation logic scattered
3. **Overlay Complexity**: AlbumCard has 4 overlays with conditional rendering
4. **Library Organization**: 30+ files need careful categorization

## Success Criteria

✅ ContextMenu: Achieved
- Main component < 200 lines
- Clear separation of concerns
- Backward compatible imports

🎯 AlbumCard: In Progress
- Main component < 150 lines
- Overlay components reusable
- Tests still passing

🎯 EditMetadataDialog: In Progress
- Main component < 120 lines
- Form fields reusable
- Validation logic isolated

📋 Library Organization: Pending
- Clear subdirectory structure
- No files at library root level
- Related components grouped

## Next Steps

1. **Complete AlbumCard & EditMetadataDialog** refactoring
2. **Reorganize library/ subdirectories**
3. **Consolidate AlbumArt duplicates**
4. **Populate shared/ui/ subdirectories**
5. **Update all import paths**
6. **Run full test suite**
7. **Create Phase 2 completion summary**

---

**Phase 2 Status**: 🔄 IN PROGRESS (5-10% complete)
**Next Phase**: Phase 3 (Shared Components Reorganization)
