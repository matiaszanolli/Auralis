# Frontend Component Consolidation Roadmap

**Status:** Planning Phase
**Last Updated:** 2025-11-22
**Priority:** High (Code Quality & Maintainability)

---

## Executive Summary

This roadmap addresses frontend component duplication, dead code, and organizational issues discovered in Phase 10 Design System Consolidation. The audit identified **865+ lines of duplicate/dead code** that should be removed or consolidated to improve maintainability and reduce cognitive load for developers.

**Key Goals:**
1. Eliminate duplicate component definitions
2. Remove orphaned/dead code (500+ lines)
3. Establish clear component hierarchy and naming conventions
4. Improve module organization (keep components under 300 lines)
5. Document consolidation patterns for future development

**Effort Estimate:** 2-3 days of focused refactoring
**Risk Level:** Low to Medium (well-scoped changes with clear test coverage)

---

## Current State Analysis

### Component Structure Overview
```
components/                             (119 total files)
├── Root level                          (10 files - LEGACY)
│   ├── AutoMasteringPane.tsx          (589 lines)
│   ├── BottomPlayerBarUnified.tsx     (395 lines) ❌ DEAD CODE
│   ├── CozyLibraryView.tsx            (397 lines)
│   ├── RadialPresetSelector.tsx       (302 lines)
│   └── ... 6 more legacy components
│
├── app-layout/                         (5 components)
│   ├── AppContainer.tsx               (Well-organized)
│   ├── AppEnhancementPane.tsx
│   ├── AppMainContent.tsx
│   ├── AppSidebar.tsx
│   └── AppTopBar.tsx
│
├── enhancement-pane-v2/                (7 components, V2 is production)
│   ├── EnhancementPaneV2.tsx          (274 lines)
│   ├── EnhancementToggle.tsx          (52 lines, re-export wrapper)
│   ├── ProcessingParameters.tsx       (Well-organized)
│   └── ... 4 more
│
├── library/                            (28 components, LARGEST DOMAIN)
│   ├── EmptyStateBox.tsx              (63 lines) ❌ REDUNDANT
│   ├── LibraryEmptyState.tsx          (58 lines) ⚠️ WRAPPER
│   ├── EmptyState.tsx                 (164 lines) ✅ CANONICAL
│   ├── GlobalSearch.tsx               (302 lines, oversized)
│   ├── TrackListView.tsx              (291 lines, at limit)
│   ├── BatchActionsToolbar.tsx        (240 lines)
│   └── ... 22 more
│
├── player-bar-v2/                      (7 components, V2 is production)
│   ├── PlayerBarV2.tsx                (Well-organized)
│   ├── EnhancementToggle.tsx          (41 lines, re-export wrapper)
│   ├── PlaybackControls.tsx
│   ├── VolumeControl.tsx
│   └── ... subfolders: lyrics/, progress/, queue/
│
├── shared/                             (15 utilities & primitives)
│   ├── EnhancementToggle.tsx          (301 lines) ✅ CANONICAL
│   ├── ContextMenu.tsx                (352 lines, generic)
│   ├── TrackContextMenu.tsx           (315 lines) ❌ OVERLAPPING
│   ├── EmptyState.tsx                 (164 lines) ✅ CANONICAL
│   ├── DropZone.tsx                   (296 lines)
│   └── ... 10 more
│
└── ... 6 other dirs (album/, navigation/, player/, playlist/, settings/, track/)
```

### Key Findings

#### 1. **Duplicate Components**
| Component | Locations | Consolidation Status |
|-----------|-----------|---------------------|
| EnhancementToggle | shared (301L) + player-bar-v2 (41L) + enhancement-pane-v2 (52L) | ✅ **GOOD** - Facade pattern |
| EmptyState | shared (164L) + library/Box (63L) + library/Wrapper (58L) | ⚠️ **NEEDS CONSOLIDATION** |
| ContextMenu | shared generic (352L) + TrackContextMenu (315L) | ⚠️ **NEEDS CONSOLIDATION** |

#### 2. **Dead Code**
| File | Status | Action |
|------|--------|--------|
| BottomPlayerBarUnified.tsx | Orphaned (no imports) | DELETE |
| BottomPlayerBarUnified.test.tsx | Orphaned test (46 cases) | DELETE |
| Total dead lines | ~500 | Remove |

#### 3. **Oversized Components** (>300 lines)
| File | Lines | Status |
|------|-------|--------|
| SettingsDialog.tsx | 652 | Oversized, needs subcomponents |
| AutoMasteringPane.tsx | 589 | Oversized, needs refactoring |
| ContextMenu.tsx | 352 | At limit (acceptable) |
| TrackContextMenu.tsx | 315 | Exceeds limit, overlaps with ContextMenu |
| CozyLibraryView.tsx | 397 | Oversized, needs decomposition |
| ArtistDetailView.tsx | 391 | Oversized, needs extraction |
| CozyArtistList.tsx | 368 | Oversized, needs subcomponents |

#### 4. **Style File Dead Exports**
| File | Unused Exports | Action |
|------|---|---|
| EmptyState.styles.ts | EmptyStateContainer, SearchEmptyState, NoResultsBox | Remove or document |
| Icon.styles.ts | SmallIconButton, MediumIconButton, LargeIconButton, IconBox | Remove or document |

#### 5. **Naming Inconsistencies**
- V2 directories exist (`player-bar-v2/`, `enhancement-pane-v2/`) but no V1 exists
  - ✅ This is acceptable - V2 is the production version
  - Could be renamed in major version (2.0+) to remove "V2" suffix
- Root-level components mixed with domain-organized subdirectories
  - Legacy: `BottomPlayerBarUnified.tsx`, `CozyLibraryView.tsx`, etc. in root
  - Current: New components organized by domain (enhancement-pane-v2/, player-bar-v2/, library/, etc.)

---

## Consolidation Phases

### Phase 1: Remove Dead Code (SAFE, NO DEPENDENCIES)

**Duration:** ~2 hours
**Risk:** None (zero imports)
**Files Affected:** 2

#### 1.1 Delete BottomPlayerBarUnified.tsx

**File:** `/auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx`

**Status:** Orphaned (verified no imports)
- ✅ Replaced by PlayerBarV2Connected in ComfortableApp.tsx
- ✅ No imports anywhere in src/
- ✅ Marked as legacy in CLAUDE.md

**Steps:**
```bash
# 1. Verify no imports
grep -r "BottomPlayerBarUnified" src/

# 2. Delete file (no fallback needed)
rm src/components/BottomPlayerBarUnified.tsx

# 3. Run tests to ensure nothing breaks
npm run test:memory
```

**Before (395 lines):**
```typescript
// Entire file used as fallback legacy player bar
// Replaced by cleaner PlayerBarV2 architecture
```

**After:** File deleted entirely

**Test Impact:** Orphaned test file exists, will address in 1.2

---

#### 1.2 Delete Orphaned Test: BottomPlayerBarUnified.test.tsx

**File:** `/auralis-web/frontend/src/components/__tests__/BottomPlayerBarUnified.test.tsx`

**Status:** Orphaned test (46 test cases)
- ✅ Tests component that no longer exists
- ✅ Should be deleted along with component

**Steps:**
```bash
# 1. Delete orphaned test
rm src/components/__tests__/BottomPlayerBarUnified.test.tsx

# 2. Run test suite
npm run test:memory
```

**Savings:** 46 test cases (no longer running)

---

### Phase 2: Consolidate EmptyState Components (MEDIUM, 4 DEPENDENCIES)

**Duration:** ~3-4 hours
**Risk:** Low (both use same pattern)
**Files Affected:** 6

#### Current State

**The Problem:**
Three separate implementations exist that do essentially the same thing:

```
Empty State Landscape:
┌─────────────────────────────────────────────────────┐
│ shared/EmptyState.tsx (164 lines) ✅ CANONICAL      │
│ - Feature-complete                                   │
│ - Predefined variants (EmptyLibrary, etc.)          │
│ - Icon type selection                                │
│ - Action button support                              │
└─────────────────────────────────────────────────────┘
         ↑
         │ (Should be used everywhere)
         │
    ┌────┴────────────────────────────────┐
    │                                      │
┌───┴──────────────────┐    ┌──────────────┴───────┐
│ library/EmptyState   │    │ library/EmptyStateBox │
│  Box.tsx (63 lines)  │    │ Wrapper.tsx (58 lines)│
│ ❌ REDUNDANT         │    │ ⚠️ WRAPPER           │
│ - Minimal props      │    │ - Router adapter     │
│ - Simple interface   │    │ - Single usage       │
└──────────────────────┘    └──────────────────────┘
```

**Current Usage Map:**

```typescript
// shared/EmptyState.tsx - Uses: 15+ imports
- enhancement-pane-v2/EnhancementPaneV2.tsx
- shared/DropZone.tsx
- shared/TrackContextMenu.tsx
- Predefined exports: EmptyLibrary, NoSearchResults, EmptyQueue, etc.

// library/EmptyStateBox.tsx - Uses: 4 imports
- library/CozyArtistList.tsx                   👈 Replace with EmptyState
- library/CozyAlbumGrid.tsx                    👈 Replace with EmptyState
- library/AlbumDetailView.tsx                  👈 Replace with EmptyState
- library/ArtistDetailView.tsx                 👈 Replace with EmptyState

// library/LibraryEmptyState.tsx - Uses: 1 import
- library/CozyLibraryView.tsx                  👈 Replace with EmptyState
```

#### Consolidation Strategy

**Step 1: Verify EmptyState Capabilities**

Check that `shared/EmptyState.tsx` can cover all use cases:

```typescript
// Current EmptyState interface
interface EmptyStateProps {
  icon?: 'music' | 'search' | 'playlist' | 'folder' | 'artist' | 'album';
  customIcon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

// EmptyStateBox uses (minimal):
// - title: string
// - subtitle: string (use as description)
// - icon: ReactNode (use as customIcon)
```

✅ **Verdict:** Full coverage - EmptyState can replace EmptyStateBox

**Step 2: Replace EmptyStateBox Usage (4 files)**

For each file using EmptyStateBox:

```typescript
// BEFORE
import { EmptyStateBox } from '@/components/library'

return <EmptyStateBox title="..." subtitle="..." icon={...} />

// AFTER
import { EmptyState } from '@/components/shared'

return <EmptyState title="..." description="..." customIcon={...} />
```

**Files to update:**
1. `/library/CozyArtistList.tsx` - Line ~340
2. `/library/CozyAlbumGrid.tsx` - Line ~290
3. `/library/AlbumDetailView.tsx` - Line ~220
4. `/library/ArtistDetailView.tsx` - Line ~180

**Steps:**
```bash
# 1. Read each file to find EmptyStateBox usage
grep -n "EmptyStateBox" src/components/library/*.tsx

# 2. Update imports and usage in each file
# 3. Delete EmptyStateBox.tsx
# 4. Run tests to verify
npm run test:memory

# 5. Verify no remaining imports
grep -r "EmptyStateBox" src/
```

**Before:**
```typescript
import { EmptyStateBox } from '@/components/library'
<EmptyStateBox title="No artists found" subtitle="Add music to your library" />
```

**After:**
```typescript
import { EmptyState } from '@/components/shared'
<EmptyState title="No artists found" description="Add music to your library" />
```

**Step 3: Handle LibraryEmptyState Wrapper (1 file)**

The `library/LibraryEmptyState.tsx` file is a simple wrapper used only by `CozyLibraryView`:

```typescript
// BEFORE: library/LibraryEmptyState.tsx - wrapper that renders shared/EmptyState
export function LibraryEmptyState() {
  return <EmptyState icon="music" title="Library is empty" />
}

// AFTER: Direct use in CozyLibraryView.tsx
import { EmptyState } from '@/components/shared'
<EmptyState icon="music" title="Library is empty" />
```

**Decision:** Delete wrapper, use EmptyState directly (simpler)

**Step 4: Clean Up Style File Exports**

File: `/library/EmptyState.styles.ts`

```typescript
// CURRENT - Has unused exports
export const EmptyStateContainer = styled.div`...`
export const SearchEmptyState = styled.div`...`
export const NoResultsBox = styled.div`...`

// AFTER - Remove or document
// These exports were never adopted and should be removed
```

**Action:** Delete unused exports or add comment:
```typescript
// Unused exports - kept for reference/future use:
// - EmptyStateContainer
// - SearchEmptyState
// - NoResultsBox
// (Actual styling done via Emotion styles in EmptyState component)
```

**Timeline:**
1. Update CozyArtistList.tsx (20 min)
2. Update CozyAlbumGrid.tsx (20 min)
3. Update AlbumDetailView.tsx (20 min)
4. Update ArtistDetailView.tsx (20 min)
5. Update CozyLibraryView.tsx (15 min)
6. Delete EmptyStateBox.tsx (5 min)
7. Delete LibraryEmptyState.tsx (5 min)
8. Clean EmptyState.styles.ts (5 min)
9. Run full test suite (5 min)

**Savings:**
- Lines deleted: 121 (EmptyStateBox + LibraryEmptyState)
- Simplified codebase: 1 less import, 1 clear source of truth
- Test coverage: Maintains existing coverage

---

### Phase 3: Consolidate ContextMenu Components (MEDIUM-HIGH, COMPLEX REFACTORING)

**Duration:** ~4-5 hours
**Risk:** Medium (requires testing playlist functionality)
**Files Affected:** 3

#### Current State

**The Problem:**
Two implementations exist with overlapping functionality but different architectural approaches:

```
Context Menu Landscape:
┌──────────────────────────────────────────────────────┐
│ shared/ContextMenu.tsx (352 lines) ✅ GENERIC       │
│ - Data-driven actions                                │
│ - Helper functions: getTrackContextActions(), etc.   │
│ - Uses: TrackQueue, CozyArtistList, PlaylistList    │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ shared/TrackContextMenu.tsx (315 lines) ❌ DUPLICATE│
│ - Track-specific menu                                │
│ - Built-in playlist loading & management            │
│ - CreatePlaylistDialog integration                   │
│ - Uses: TrackRow (specialized)                       │
└──────────────────────────────────────────────────────┘
```

**Architecture Comparison:**

```typescript
// ContextMenu - Generic, composition-based
interface ContextMenuProps {
  items: ContextMenuAction[]
  onAction: (action: ContextMenuAction) => void
}

// Usage with helper functions:
const actions = getTrackContextActions(track)
<ContextMenu items={actions} onAction={handleAction} />

// vs.

// TrackContextMenu - Specialized, self-contained
interface TrackContextMenuProps {
  track: Track
  onAddToPlaylist: (playlistId) => void
  onRemoveFromPlaylist?: (playlistId) => void
}

// Usage - all logic encapsulated:
<TrackContextMenu track={track} onAddToPlaylist={handler} />
// Internally: loads playlists, shows dialog, manages state
```

**Key Differences:**

| Aspect | ContextMenu | TrackContextMenu |
|--------|-------------|------------------|
| Approach | Data-driven (actions array) | Specialized (hardcoded) |
| Customization | High (configure actions) | Low (fixed menu) |
| Playlist support | Via getTrackContextActions | Built-in, dynamic |
| Dialog integration | External | Built-in CreatePlaylistDialog |
| Lines | 352 | 315 |
| Reusability | High (used 3+ places) | Low (Track-only) |

#### Consolidation Strategy

**Goal:** Merge TrackContextMenu into ContextMenu as optional feature module

**Step 1: Analyze Playlist-Specific Logic**

Extract from TrackContextMenu:
```typescript
const [playlists, setPlaylists] = useState<Playlist[]>([])
const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false)
const [showCreateDialog, setShowCreateDialog] = useState(false)

// Playlist loading
const fetchPlaylists = async () => {...}

// Playlist management
const handleAddToPlaylist = (playlistId: number) => {...}
const handleCreatePlaylist = (name: string) => {...}
```

**Step 2: Extend ContextMenu Interface**

Add optional playlist section props:

```typescript
interface ContextMenuProps {
  // Existing
  items: ContextMenuAction[]
  onAction?: (action: ContextMenuAction) => void

  // New: Optional playlist section
  showPlaylistSection?: boolean
  playlists?: Playlist[]
  isLoadingPlaylists?: boolean
  onAddToPlaylist?: (playlistId: number) => void
  onCreatePlaylist?: (name: string) => void
}
```

**Step 3: Refactor Rendering**

Add conditional playlist section in ContextMenu:

```typescript
{showPlaylistSection && (
  <Divider />
  <Subheader>Add to Playlist</Subheader>
  {isLoadingPlaylists ? (
    <MenuItem disabled>Loading playlists...</MenuItem>
  ) : (
    <>
      {playlists.map(playlist => (
        <MenuItem key={playlist.id} onClick={() => onAddToPlaylist(playlist.id)}>
          {playlist.name}
        </MenuItem>
      ))}
      <MenuItem onClick={() => setShowCreateDialog(true)}>
        ➕ Create new playlist
      </MenuItem>
    </>
  )}
  {showCreateDialog && (
    <CreatePlaylistDialog
      open={true}
      onClose={() => setShowCreateDialog(false)}
      onCreate={onCreatePlaylist}
    />
  )}
)}
```

**Step 4: Update TrackRow Component**

Change from TrackContextMenu to ContextMenu with playlist feature:

**Before:**
```typescript
import { TrackContextMenu } from '@/components/shared'

<TrackContextMenu
  track={track}
  onAddToPlaylist={handleAddToPlaylist}
/>
```

**After:**
```typescript
import { ContextMenu, getTrackContextActions } from '@/components/shared'

const [playlists, setPlaylists] = useState<Playlist[]>([])
const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false)

// Load playlists on mount
useEffect(() => {
  fetchPlaylists()
}, [])

<ContextMenu
  items={getTrackContextActions(track)}
  onAction={handleAction}
  showPlaylistSection
  playlists={playlists}
  isLoadingPlaylists={isLoadingPlaylists}
  onAddToPlaylist={handleAddToPlaylist}
  onCreatePlaylist={handleCreatePlaylist}
/>
```

**Step 5: Delete TrackContextMenu**

After migration:
```bash
rm src/components/shared/TrackContextMenu.tsx
rm src/components/shared/__tests__/TrackContextMenu.test.tsx  (if exists)
```

**Step 6: Update Tests**

Ensure ContextMenu tests cover playlist functionality:
- Test playlist section rendering
- Test playlist item clicks
- Test create playlist dialog integration
- Verify TrackRow context menu works as before

**Timeline:**
1. Analyze TrackContextMenu logic (30 min)
2. Extend ContextMenu interface (20 min)
3. Implement playlist section in ContextMenu (40 min)
4. Update getTrackContextActions if needed (20 min)
5. Update TrackRow to use unified ContextMenu (30 min)
6. Update/add tests (60 min)
7. Delete TrackContextMenu (5 min)
8. Full test run (10 min)

**Savings:**
- Lines deleted: 315 (TrackContextMenu)
- Increased reusability: ContextMenu now handles all menu scenarios
- Single source of truth: One component for all context menus
- Better maintainability: Playlist logic in one place

**Risk Mitigation:**
- ✅ Comprehensive test coverage exists for both components
- ✅ Clear API boundaries (context menu actions)
- ⚠️ Must test playlist add/create workflow thoroughly
- ⚠️ Integration tests for TrackRow context menu needed

---

### Phase 4: Address Oversized Components (DEFERRED, FUTURE WORK)

**Duration:** ~8-10 hours across multiple sessions
**Risk:** Medium (complex refactoring, might break UI)
**Files Affected:** 6

**Note:** These are large enough to warrant separate refactoring efforts. Phase 4 should be deferred until Phases 1-3 are complete.

#### Components Exceeding 300-Line Limit

| Component | Lines | Complexity | Priority |
|-----------|-------|-----------|----------|
| SettingsDialog.tsx | 652 | High (many settings) | Medium |
| AutoMasteringPane.tsx | 589 | High (processing UI) | Medium |
| CozyLibraryView.tsx | 397 | High (main view) | Low |
| ArtistDetailView.tsx | 391 | High (detail view) | Low |
| CozyArtistList.tsx | 368 | Medium (list with features) | Low |
| GlobalSearch.tsx | 302 | High (search logic) | Low |

#### Approach (Future Work)

**SettingsDialog (652 lines):**
```
Extract subcomponents:
├── SettingsSection.tsx (reusable wrapper)
├── PlaybackSettingsSection.tsx (extract)
├── EnhancementSettingsSection.tsx (extract)
├── LibrarySettingsSection.tsx (extract)
└── DisplaySettingsSection.tsx (extract)
```

**AutoMasteringPane (589 lines):**
```
Extract subcomponents:
├── ProcessingModeSelector.tsx (extract)
├── PresetControls.tsx (extract)
├── AudioFeaturesDisplay.tsx (extract)
└── ProcessingStatusDisplay.tsx (extract)
```

**CozyLibraryView (397 lines):**
```
Extract subcomponents:
├── LibraryViewContent.tsx (main list/grid)
├── LibraryDetailPanel.tsx (detail view)
├── LibraryActions.tsx (header actions)
└── LibraryState.tsx (state management hook)
```

**Future Ticket Template:**
```markdown
## Refactor [ComponentName] to Modular Structure

### Current Issue
- Component exceeds 300-line limit (XXX lines)
- Multiple responsibilities: [list]
- Difficult to test individual features

### Proposed Solution
Extract subcomponents:
- [SubComponent1].tsx
- [SubComponent2].tsx
- [SubComponent3].tsx

### Expected Outcome
- Each subcomponent < 250 lines
- Clear separation of concerns
- Improved testability
- No behavior changes (interface compatibility)

### Testing Strategy
- Existing tests should pass without modification
- Add new tests for extracted subcomponents
```

**Deferral Rationale:**
- These require careful UI testing
- Lower impact than duplicate code
- Better done incrementally with feature work
- Schedule for next major refactoring cycle

---

### Phase 5: Clean Up Style File Exports (QUICK, OPTIONAL)

**Duration:** ~1 hour
**Risk:** None (cleanup only)
**Files Affected:** 2

#### Identified Dead Exports

**File 1: `/library/EmptyState.styles.ts`**
```typescript
// Unused exports
export const EmptyStateContainer = styled.div`...`
export const SearchEmptyState = styled.div`...`
export const NoResultsBox = styled.div`...`
```

**Reason:** These predefined styled components were never adopted. The actual EmptyState component uses inline Emotion styles.

**Decision Options:**
1. **Delete immediately** - If confident they're not needed
2. **Keep with JSDoc comment** - Document why they exist:
   ```typescript
   /**
    * Legacy exports kept for reference.
    * Current EmptyState implementation uses inline Emotion styles.
    * These can be deleted if confirmed unused in future versions.
    */
   ```

**File 2: `/library/Icon.styles.ts`**
```typescript
// Unused exports
export const SmallIconButton = styled.button`...`
export const MediumIconButton = styled.button`...`
export const LargeIconButton = styled.button`...`
export const IconBox = styled.div`...`
```

**Reason:** Generic button styles that components prefer MUI's IconButton component for.

**Decision Options:**
1. **Delete immediately** - If MUI is the standard
2. **Keep with comment** - Document deprecation:
   ```typescript
   /**
    * @deprecated Use MUI's IconButton component instead.
    * These legacy styled components are kept for reference only.
    */
   ```

#### Action Items

**Choice A: Immediate Cleanup**
```bash
# Remove unused exports from files
# Keep comments documenting removal

# Verify no imports
grep -r "EmptyStateContainer\|SearchEmptyState\|NoResultsBox\|SmallIconButton\|MediumIconButton" src/
```

**Choice B: Documented Deprecation**
```typescript
// Mark as deprecated with JSDoc comments
// Schedule for removal in 2.0 release
```

**Recommendation:** **Choice A** - Delete unused exports immediately
- Cleaner codebase
- No risk (verified no imports)
- These can be re-added if needed in future

---

## Implementation Timeline

### Week 1: Remove Dead Code + Empty State Consolidation

**Phase 1: Remove Dead Code** (Day 1, ~2 hours)
- Delete BottomPlayerBarUnified.tsx
- Delete BottomPlayerBarUnified.test.tsx
- Verify no import errors
- Run test suite

**Phase 2: Consolidate EmptyState** (Days 1-2, ~3-4 hours)
- Update 4 component imports (CozyArtistList, CozyAlbumGrid, AlbumDetailView, ArtistDetailView)
- Delete EmptyStateBox.tsx
- Delete LibraryEmptyState.tsx
- Clean EmptyState.styles.ts
- Run tests

**Review & Checkpoint:** (Day 2, 1 hour)
- Code review: Verify all changes working
- Test run: npm run test:memory
- Git commit: "refactor: consolidate empty state components"

### Week 2: ContextMenu Consolidation

**Phase 3: Consolidate ContextMenu** (Days 3-5, ~4-5 hours)
- Analyze TrackContextMenu logic (30 min)
- Extend ContextMenu interface (20 min)
- Implement playlist section (40 min)
- Update TrackRow component (30 min)
- Update/write tests (60 min)
- Delete TrackContextMenu.tsx (5 min)
- Full test run (10 min)

**Review & Checkpoint:** (Day 5, 1 hour)
- Code review: Verify playlist functionality works
- Integration tests: Test TrackRow context menu thoroughly
- Git commit: "refactor: merge TrackContextMenu into unified ContextMenu"

### Phase 4: Cleanup & Documentation (Day 5, ~2 hours)

**Phase 5: Clean Style Exports** (30 min)
- Delete unused exports from Icon.styles.ts and EmptyState.styles.ts
- Verify no errors

**Documentation Updates** (1.5 hours)
- Update CLAUDE.md to reflect new consolidation
- Document component patterns (EnhancementToggle wrapper pattern)
- Create COMPONENT_PATTERNS.md guide
- Update COMPONENT_CONSOLIDATION_ROADMAP.md status

**Final Testing & Commit** (30 min)
- Full test suite: npm run test:memory
- Build verification: npm run build
- Final commit: "docs: update component organization after consolidation"

---

## Success Criteria

### Phase 1 Completion
- [ ] BottomPlayerBarUnified.tsx deleted
- [ ] BottomPlayerBarUnified.test.tsx deleted
- [ ] All tests passing
- [ ] Zero import errors for deleted files

### Phase 2 Completion
- [ ] EmptyStateBox.tsx deleted
- [ ] LibraryEmptyState.tsx deleted
- [ ] All 4 consumers updated to use EmptyState
- [ ] Unused style exports removed from EmptyState.styles.ts
- [ ] All library tests passing
- [ ] No visual regressions (same UI output)

### Phase 3 Completion
- [ ] TrackContextMenu.tsx deleted
- [ ] ContextMenu.tsx extended with playlist section
- [ ] TrackRow updated to use unified ContextMenu
- [ ] Playlist add/create functionality working
- [ ] All context menu tests passing
- [ ] No visual regressions

### Phase 4 Completion
- [ ] Unused style exports deleted or documented
- [ ] No broken imports
- [ ] All tests passing

### Overall Success
- [ ] ~865 lines of duplicate/dead code removed
- [ ] 4 files deleted entirely
- [ ] ~10 files modified for consolidation
- [ ] All tests passing (npm run test:memory)
- [ ] Clean build (npm run build)
- [ ] Documentation updated

---

## Documentation Updates Needed

### 1. Update CLAUDE.md
Add to "⚠️ Important Gotchas" section:
```markdown
### Component Consolidation & Organization

**Current Structure (Phase 10+ Complete):**
- Root-level legacy components being migrated to domain-organized subdirectories
- Canonical/reusable components in `shared/` with domain-specific wrappers (EnhancementToggle pattern)
- Large feature domains have dedicated directories: enhancement-pane-v2/, player-bar-v2/, library/, etc.
- Each component should stay < 300 lines (use facade pattern for larger features)

**Key Consolidation Decisions:**
- **EnhancementToggle:** One source (shared), two re-export wrappers with variant selection
- **EmptyState:** One canonical implementation (shared/EmptyState.tsx) - DO NOT create variants
- **ContextMenu:** One unified component (shared/ContextMenu) handles all menu types
- **BottomPlayerBarUnified:** DELETED - use PlayerBarV2/PlayerBarV2Connected instead

**When Adding New Components:**
1. Avoid creating "V2" or duplicate versions of existing components
2. Keep components under 300 lines (extract subcomponents if needed)
3. Use shared components as single source of truth
4. Consider whether it's a reusable primitive or domain-specific component
```

### 2. Create COMPONENT_PATTERNS.md
```markdown
# Frontend Component Architecture Patterns

## Pattern 1: Facade Re-exports
Used when a component should be used in multiple contexts with different configurations.

**Example: EnhancementToggle**
- Main implementation: `shared/EnhancementToggle.tsx` (301 lines)
- Variant 1: `player-bar-v2/EnhancementToggle.tsx` → `variant="button"` preset
- Variant 2: `enhancement-pane-v2/EnhancementToggle.tsx` → `variant="switch"` preset

**When to use:**
- Component needs same behavior, different presentation in different contexts
- Avoid cluttering the main component with conditional styling
- Makes consuming code clearer (intent is explicit)

## Pattern 2: Composition-Based Menus
Used for flexible, data-driven context menus.

**Example: ContextMenu**
- Define actions: `ContextMenuAction[]`
- Pass to menu: `<ContextMenu items={actions} />`
- Helper functions: `getTrackContextActions()`, `getAlbumContextActions()`

**When to use:**
- Menu items are dynamic or context-dependent
- Multiple components need similar menus with different actions
- Avoid: hardcoding menu items in component

## Pattern 3: Single Source of Truth
Components should have ONE canonical implementation.

**Example: EmptyState**
- One implementation: `shared/EmptyState.tsx`
- Used everywhere (library, enhancement-pane, dropzone, etc.)
- DO NOT create: EmptyStateBox, EmptyStateWrapper, LibraryEmptyState variants

**When to use:**
- Component is a UI primitive or reusable utility
- Same behavior needed in multiple places
- Avoid: Creating specialized "X-specific" versions (use props instead)
```

### 3. Update Component Index Documentation
Add to relevant README files:
```markdown
## Component Organization

**Shared UI Primitives** (`components/shared/`)
- Universal components: EnhancementToggle, ContextMenu, EmptyState, etc.
- Use these as single source of truth
- Extend via props, don't duplicate

**Domain-Specific Components** (`components/<domain>/`)
- Feature-specific: enhancement-pane-v2/, player-bar-v2/, library/, etc.
- Co-locate tests in `__tests__/` subdirectories
- Extract subcomponents if file > 300 lines

**Style Files** (`components/library/*.styles.ts`)
- Design tokens consolidated in Phase 10
- Use shared tokens: `auroraOpacity`, `gradients`, etc.
- Document any dead exports clearly
```

---

## Git Commit Messages

Phase 1:
```
refactor: remove dead code - BottomPlayerBarUnified component

- Delete unused BottomPlayerBarUnified.tsx (395 lines)
- Delete orphaned test file (46 test cases)
- Component was replaced by PlayerBarV2 architecture
- Verified zero imports across codebase
- All tests passing
```

Phase 2:
```
refactor: consolidate empty state components to single implementation

- Delete EmptyStateBox.tsx (63 lines) - redundant with EmptyState
- Delete LibraryEmptyState.tsx (58 lines) - simple wrapper
- Update 4 consumers to use shared/EmptyState:
  - CozyArtistList.tsx
  - CozyAlbumGrid.tsx
  - AlbumDetailView.tsx
  - ArtistDetailView.tsx
- Remove unused exports from EmptyState.styles.ts
- Simplifies codebase: 1 import path for empty states
- All tests passing, no visual changes
```

Phase 3:
```
refactor: consolidate context menus into unified ContextMenu

- Merge TrackContextMenu logic into ContextMenu component
- Add optional playlist section to ContextMenu interface
- Update TrackRow to use unified ContextMenu with getTrackContextActions
- Delete TrackContextMenu.tsx (315 lines)
- Improves reusability and maintainability
- Playlist add/create functionality verified
- All context menu tests passing
```

Phase 4:
```
refactor: clean up unused style exports

- Delete unused exports from Icon.styles.ts:
  SmallIconButton, MediumIconButton, LargeIconButton, IconBox
- Prefer MUI's IconButton component instead
- No functionality impact (dead code removal)
```

Phase 5 (Documentation):
```
docs: update component organization after consolidation phases

- Add component organization patterns to CLAUDE.md
- Create COMPONENT_PATTERNS.md with architecture guide
- Document canonical components (EnhancementToggle, EmptyState, ContextMenu)
- Update component index documentation
- Reference consolidation roadmap for future work
```

---

## Risk Assessment

### Phase 1: Remove Dead Code
- **Risk Level:** ✅ **NONE**
- **Mitigation:** Verified zero imports, clean deletion
- **Rollback:** Simple re-add from git if needed

### Phase 2: Consolidate EmptyState
- **Risk Level:** 🟢 **LOW**
- **Mitigation:** Both implementations use same pattern, extensive tests
- **Rollback:** Re-add EmptyStateBox and LibraryEmptyState from git

### Phase 3: Consolidate ContextMenu
- **Risk Level:** 🟡 **MEDIUM**
- **Mitigation:** Comprehensive test coverage, isolated changes to playlist section
- **Rollback:** Keep TrackContextMenu branch for quick revert if needed

### Phase 4: Clean Style Exports
- **Risk Level:** ✅ **NONE**
- **Mitigation:** Verified zero imports before deletion
- **Rollback:** Re-add from git if needed

### Overall Risk Mitigation
- ✅ Run full test suite after each phase: `npm run test:memory`
- ✅ Build verification: `npm run build`
- ✅ Commit frequently with clear messages
- ✅ Create rollback branches before each phase if needed
- ✅ Code review before final merge

---

## Future Work & TODOs

### TODO 1: Extract Oversized Components (Phase 4 - Deferred)
- [ ] SettingsDialog.tsx (652 lines) - Extract into 5 subcomponents
- [ ] AutoMasteringPane.tsx (589 lines) - Extract into 4 subcomponents
- [ ] CozyLibraryView.tsx (397 lines) - Extract into 3 subcomponents
- [ ] ArtistDetailView.tsx (391 lines) - Extract into 2-3 subcomponents
- [ ] CozyArtistList.tsx (368 lines) - Extract into subcomponents
- [ ] GlobalSearch.tsx (302 lines) - Extract search logic into hook

### TODO 2: Rename V2 Components (Major Version 2.0+)
- [ ] Rename `player-bar-v2/` → `player-bar/` (remove "V2" suffix)
- [ ] Rename `enhancement-pane-v2/` → `enhancement-pane/` (remove "V2" suffix)
- [ ] Update all imports accordingly
- [ ] Schedule for version 2.0 release

### TODO 3: Create Component Registry
- [ ] Document all components in single registry file
- [ ] List canonical vs. deprecated components
- [ ] Show import paths and usage examples
- [ ] Add to project docs

### TODO 4: Implement Linting Rules
- [ ] Add ESLint rule to prevent "V2" naming
- [ ] Add rule to limit component files to 300 lines
- [ ] Add rule to detect and warn about duplicate component patterns
- [ ] Integrate into pre-commit hooks

### TODO 5: Test Coverage Improvements
- [ ] Increase ContextMenu test coverage (playlist section)
- [ ] Add integration tests for consolidated components
- [ ] Verify no visual regressions with snapshot tests

---

## References

### Related Documentation
- **Design System:** Phase 10 Consolidation complete (170+ duplicate colors removed)
- **Component Guidelines:** See CLAUDE.md "Component Guidelines" section
- **Testing Standards:** See TESTING_GUIDELINES.md
- **Architecture:** MULTI_TIER_BUFFER_ARCHITECTURE.md for context

### Commands Reference
```bash
# View component tree
find src/components -type f -name "*.tsx" | sort

# Check imports
grep -r "ImportName" src/

# Count component lines
find src/components -name "*.tsx" -exec wc -l {} + | sort -rn

# Run full tests
npm run test:memory

# Build verification
npm run build

# Git operations
git log --oneline          # View recent commits
git branch -b refactor/*   # Create refactor branch
git diff src/components/   # View changes
```

---

## Approval & Sign-Off

**Status:** 📋 Ready for Implementation

**Next Steps:**
1. Review this roadmap with team
2. Get approval to proceed with Phase 1
3. Create implementation branch: `git checkout -b refactor/component-consolidation`
4. Follow phases sequentially with testing between each
5. Update this document as phases complete

**Estimated Timeline:** 2-3 days of focused work
**Team Size:** 1 developer recommended (minimize merge conflicts)
**Priority:** High (Code Quality & Maintainability)

---

**Last Updated:** 2025-11-22 by Claude Code
**Status:** Planning Complete - Ready to Implement
