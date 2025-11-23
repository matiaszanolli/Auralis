# Phase 5: Component Extraction & Refactoring
## Comprehensive Implementation Plan

**Status**: 🎯 Ready for Execution
**Target Timeline**: 3-4 weeks (21-27 hours effort)
**Current Code**: 2,308 total lines across 6 components
**Target After**: <1,200 total lines (48% reduction)

---

## Executive Summary

Phase 5 completes the frontend consolidation by extracting logic from 6 oversized components into smaller, focused subcomponents. This maintains all functionality while dramatically improving maintainability and testability.

**Expected Impact:**
- ✅ 1,100+ lines of code refactored
- ✅ 28 new subcomponents created
- ✅ 3 custom hooks extracted
- ✅ 25-30 new test files
- ✅ 100% backward compatibility (no breaking changes)
- ✅ Improved code clarity and testability

---

## Components to Extract

### Phase 5A: Week 1 (6-8 hours)

#### 1. SettingsDialog.tsx (652 lines)
**Location**: `src/components/settings/SettingsDialog.tsx`

**Current Structure:**
- Single massive dialog component
- 7 distinct setting categories
- Tab-based navigation
- Mixed UI + business logic

**Extraction Plan:**
```
SettingsDialog (main, ~100 lines)
├── SettingsTabNav (~40 lines)
├── LibrarySettingsPanel (~80 lines)
├── PlaybackSettingsPanel (~90 lines)
├── AudioSettingsPanel (~95 lines)
├── InterfaceSettingsPanel (~80 lines)
├── EnhancementSettingsPanel (~100 lines)
└── AdvancedSettingsPanel (~75 lines)
```

**Extraction Steps:**
1. Extract tab navigation logic → `SettingsTabNav.tsx`
2. Extract each settings panel into separate component
3. Create shared `useSettings` hook for state management
4. Update tests (target: 7 new test files)
5. Verify all settings persist and load correctly

**Key Considerations:**
- Settings persistence (localStorage/server)
- Form validation across all panels
- Radio buttons, toggles, sliders in different panels
- No state passed to children—each uses custom hook

**Success Criteria:**
- [ ] All 7 components < 100 lines
- [ ] SettingsDialog main < 100 lines
- [ ] All tests passing
- [ ] No breaking changes to settings API
- [ ] Settings still persist correctly

---

#### 2. GlobalSearch.tsx (301 lines)
**Location**: `src/components/library/GlobalSearch.tsx`

**Current Structure:**
- Multi-type search (tracks, albums, artists)
- Results grouping by type
- Debounced API calls
- Keyboard navigation

**Extraction Plan:**
```
GlobalSearch (main, ~80 lines)
├── SearchInput (~50 lines)
├── ResultsContainer (~40 lines)
├── ResultGroup (~45 lines)
├── ResultAvatar (~30 lines)
└── useSearchLogic hook (~95 lines)
```

**Extraction Steps:**
1. Extract search input component → `SearchInput.tsx`
2. Extract results container → `ResultsContainer.tsx`
3. Extract result grouping logic → `ResultGroup.tsx`
4. Extract avatar display → `ResultAvatar.tsx`
5. Extract search logic to custom hook → `useSearchLogic.ts`
6. Update tests (target: 5 new test files)

**Hook Details (useSearchLogic):**
- State: query, results, loading, selectedIndex
- Functions: handleSearch (debounced), handleKeyDown, handleSelect
- Dependencies: playlistService, trackService, albumService, artistService
- Features: type-based result grouping, smart filtering

**Key Considerations:**
- 300ms debounce on search queries
- Multiple simultaneous API calls
- Result grouping by type (tracks > albums > artists)
- Keyboard navigation (arrow keys, enter)
- Empty state handling

**Success Criteria:**
- [ ] All 4 components < 80 lines
- [ ] useSearchLogic < 100 lines
- [ ] Debounce working correctly
- [ ] Keyboard navigation preserved
- [ ] Result grouping consistent
- [ ] All tests passing

---

### Phase 5B: Week 2 (7-9 hours)

#### 3. ArtistDetailView.tsx (398 lines)
**Location**: `src/components/library/ArtistDetailView.tsx`

**Current Structure:**
- Artist header section
- Albums grid
- Tracks list
- Loading states

**Extraction Plan:**
```
ArtistDetailView (main, ~120 lines)
├── ArtistHeader (~90 lines)
├── AlbumsTab (~80 lines)
├── TracksTab (~75 lines)
└── DetailLoading (~50 lines)
```

**Extraction Steps:**
1. Extract artist header → `ArtistHeader.tsx` (bio, image, stats)
2. Extract albums grid → `AlbumsTab.tsx` (grid rendering, context menu)
3. Extract tracks list → `TracksTab.tsx` (track rows, sorting)
4. Extract loading state → `DetailLoading.tsx` (skeleton screens)
5. Update tests (target: 4 new test files)

**Key Considerations:**
- Tab switching (Albums ↔ Tracks)
- Grid vs list layout
- Context menus on albums and tracks
- Loading skeleton with correct dimensions
- Back button functionality

**Success Criteria:**
- [ ] All 4 components < 100 lines
- [ ] Main view < 120 lines
- [ ] Tab switching works seamlessly
- [ ] Context menus work on albums/tracks
- [ ] Loading state displays correctly
- [ ] All tests passing

---

#### 4. CozyLibraryView.tsx (398 lines)
**Location**: `src/components/library/CozyLibraryView.tsx`

**Current Structure:**
- View mode switching (grid/list)
- Search + filtering
- Sorting options
- Content rendering
- Keyboard shortcuts

**Note**: This component was already partially refactored in earlier phases (from 958 → 398 lines). Further extraction is lower priority due to complex orchestration needs.

**Extraction Plan:**
```
CozyLibraryView (main, ~240 lines - remains larger)
├── LibrarySearchControls (~70 lines)
└── useLibraryKeyboardShortcuts hook (~65 lines)
```

**Extraction Steps:**
1. Extract search/filter controls → `LibrarySearchControls.tsx`
2. Extract keyboard shortcut logic → `useLibraryKeyboardShortcuts.ts`
3. Update tests (target: 2 new test files)

**Hook Details (useLibraryKeyboardShortcuts):**
- Ctrl+A: Select all items
- Escape: Clear selection
- Shift+Click: Range select
- Keyboard focus management
- Cleanup on unmount

**Key Considerations:**
- Complex state orchestration (search, filter, sort, view mode)
- Keyboard shortcuts interact with search input
- Selection state management across view modes
- Event bubbling and focus management

**Success Criteria:**
- [ ] Search controls < 70 lines
- [ ] Keyboard hook < 65 lines
- [ ] Keyboard shortcuts work correctly
- [ ] Selection state preserved
- [ ] No breaking changes to layout
- [ ] All tests passing

---

### Phase 5C: Week 3 (8-10 hours)

#### 5. CozyArtistList.tsx (368 lines)
**Location**: `src/components/library/CozyArtistList.tsx`

**Current Structure:**
- Infinite scroll pagination
- Alphabetic grouping (A-Z)
- Artist item rendering
- Loading indicators
- Empty states

**Extraction Plan:**
```
CozyArtistList (main, ~80 lines)
├── ArtistListItem (~60 lines)
├── ArtistSection (~50 lines)
├── PaginationButton (~35 lines)
├── ListLoading (~40 lines)
└── useArtistListPagination hook (~120 lines)
```

**Extraction Steps:**
1. Extract artist item → `ArtistListItem.tsx` (avatar, name, interaction)
2. Extract section heading → `ArtistSection.tsx` (letter header)
3. Extract pagination button → `PaginationButton.tsx` (load more)
4. Extract loading skeleton → `ListLoading.tsx`
5. Extract pagination logic → `useArtistListPagination.ts`
6. Update tests (target: 5 new test files)

**Hook Details (useArtistListPagination):**
- State: artists, offset, hasMore, isLoadingMore, totalArtists, alphabetGroups
- Functions: loadMore, groupByLetter, getVisibleArtists
- Dependencies: artistService
- Features: infinite scroll, letter grouping, performance optimization

**Key Considerations:**
- Infinite scroll with intersection observer
- Alphabetic grouping (A-Z sections)
- Pagination with offset-based API
- Virtual scrolling consideration for large lists
- Loading more indicator
- Empty state when no artists

**Success Criteria:**
- [ ] All 4 components < 65 lines
- [ ] Hook < 130 lines
- [ ] Infinite scroll works smoothly
- [ ] Letter grouping correct
- [ ] No n+1 API calls
- [ ] Performance acceptable (>60 FPS)
- [ ] All tests passing

---

#### 6. AutoMasteringPane.tsx (589 lines)
**Location**: `src/components/AutoMasteringPane.tsx`

**Status**: 🗑️ DEPRECATED (DO NOT EXTRACT)

**Action Plan:**
1. Verify AutoMasteringPane is unused (search imports)
2. Confirm EnhancementPaneV2 has all needed functionality
3. Delete file completely
4. Remove from imports across codebase
5. Update tests to use EnhancementPaneV2

**Success Criteria:**
- [ ] File deleted
- [ ] Zero imports found
- [ ] Verified with EnhancementPaneV2
- [ ] All tests pass with new component

**Impact**: Removes 589 lines of unused code, reduces maintenance burden

---

## Implementation Timeline

### Week 1: Phase 5A
**Duration**: 6-8 hours
**Components**: SettingsDialog + GlobalSearch
**Deliverables**:
- 9 new subcomponents (SettingsDialog + GlobalSearch)
- 2 custom hooks (useSettings, useSearchLogic)
- 12 new test files
- 2 PRs (one per component)

**Weekly Goals**:
- [ ] SettingsDialog extracted (7 panels + nav)
- [ ] GlobalSearch extracted (4 components + hook)
- [ ] All tests passing
- [ ] PRs reviewed and merged
- [ ] Build stable (4-5 sec)

---

### Week 2: Phase 5B
**Duration**: 7-9 hours
**Components**: ArtistDetailView + CozyLibraryView
**Deliverables**:
- 6 new subcomponents (ArtistDetail + LibraryView)
- 1 custom hook (useLibraryKeyboardShortcuts)
- 6 new test files
- 2 PRs

**Weekly Goals**:
- [ ] ArtistDetailView extracted (header, albums, tracks, loading)
- [ ] CozyLibraryView controls extracted
- [ ] Keyboard shortcuts working
- [ ] All tests passing
- [ ] PRs reviewed and merged

---

### Week 3: Phase 5C
**Duration**: 8-10 hours
**Components**: CozyArtistList + AutoMasteringPane cleanup
**Deliverables**:
- 4 new subcomponents (CozyArtistList)
- 1 custom hook (useArtistListPagination)
- 5 new test files
- 1 PR (component extraction) + 1 cleanup PR

**Weekly Goals**:
- [ ] CozyArtistList extracted (items, sections, pagination hook)
- [ ] Infinite scroll working smoothly
- [ ] AutoMasteringPane deprecated
- [ ] All tests passing
- [ ] PRs reviewed and merged

---

## Detailed Extraction Checklist

### Pre-Extraction (Per Component)

- [ ] Read entire component thoroughly
- [ ] Identify all props/state/callbacks
- [ ] Map out component hierarchy
- [ ] List all test cases
- [ ] Check for component re-exports
- [ ] Document current API surface
- [ ] Create feature branch: `refactor/extract-{component}`

### Extraction Process

- [ ] Create subcomponent file
- [ ] Move logic from parent
- [ ] Update imports in parent
- [ ] Pass props down properly
- [ ] Test subcomponent in isolation
- [ ] Run parent tests
- [ ] Run entire test suite
- [ ] Verify TypeScript (npm build)
- [ ] Check build time (should be stable)

### Post-Extraction

- [ ] Create test file for subcomponent
- [ ] Verify no breaking changes
- [ ] Check for unused imports
- [ ] Run linter/formatter
- [ ] Update inline documentation
- [ ] Create PR with clear description
- [ ] Request code review
- [ ] Address feedback
- [ ] Merge to master

### Testing & QA

- [ ] Unit tests for each subcomponent
- [ ] Integration tests (parent + children)
- [ ] Visual regression testing
- [ ] Manual feature testing
- [ ] Keyboard navigation testing
- [ ] Loading state testing
- [ ] Error state testing
- [ ] Performance profiling
- [ ] Accessibility audit (if applicable)

---

## Git Workflow

### Branch Naming
- Feature branches: `refactor/extract-{component-name}`
- Examples:
  - `refactor/extract-settings-dialog`
  - `refactor/extract-global-search`
  - `refactor/extract-artist-detail`
  - etc.

### Commit Strategy
- **One commit per subcomponent** (atomic commits)
- Format: `refactor: extract {SubcomponentName} from {ParentComponent}`
- Include line count reduction in commit message
- Example:
  ```
  refactor: extract SettingsTabNav from SettingsDialog

  - Extract tab navigation logic into separate component
  - Remove 50 lines from SettingsDialog (652 → 602)
  - Add SettingsTabNav.tsx (40 lines)
  - Update tests for new component structure
  - All tests passing, build successful (4.35s)
  ```

### PR Guidelines
- **One PR per component** (not per subcomponent)
- Title: `refactor: extract subcomponents from {Component}`
- Description should include:
  - Component breakdown diagram
  - Lines removed/added
  - Testing approach
  - Screenshots/visual verification
  - Checklist of all subcomponents

### Code Review
- Focus on: Correctness, TypeScript types, tests, imports
- Verify: No behavior changes, tests passing, build clean
- Check: No circular dependencies, proper prop passing

---

## Testing Strategy

### Unit Tests
- **Per subcomponent**: Test in isolation
- Props, state, callbacks, event handlers
- Edge cases, error states, empty states

### Integration Tests
- Parent + child components together
- Props flow correctly
- Callbacks propagate correctly
- State stays in sync

### Regression Tests
- Original component tests should still pass
- No behavioral changes
- Same user interactions work
- Same API surface

### Test Coverage
- **Target**: ≥55% (maintain current level)
- **Method**: Jest + React Testing Library
- **Files**: Mirror source structure
  - `Parent.tsx` → `Parent.test.tsx`
  - `SubcomponentA.tsx` → `SubcomponentA.test.tsx`

---

## Risk Mitigation

### Risk: Circular Dependencies
**Mitigation**:
- Plan import paths carefully before extraction
- Create visual dependency graph
- Test imports explicitly
- Use `npm build` to catch early

### Risk: TypeScript Errors
**Mitigation**:
- Define props interfaces first
- Use strict type checking
- Test build frequently
- Verify with `npm build` after each extraction

### Risk: Test Coverage Drop
**Mitigation**:
- Add tests for each new component
- Maintain >55% coverage
- Run full test suite frequently
- Check coverage reports

### Risk: Performance Regression
**Mitigation**:
- Profile before and after extraction
- Track build time (target: 4-5 sec)
- Monitor bundle size
- Test with larger datasets

### Risk: Breaking Changes
**Mitigation**:
- No external API changes
- Props/callbacks stay identical
- Document all changes clearly
- Review imports carefully

---

## Success Metrics

### Code Quality
| Metric | Target | Validation |
|--------|--------|-----------|
| All components < 300 lines | 100% | Code review |
| Test pass rate | ≥95% | Test suite |
| Code coverage | ≥55% | Coverage report |
| TypeScript errors | 0 | Build log |
| Build time | 4-5 sec | Build log |
| Breaking changes | 0 | Import check |

### Component Metrics
| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| SettingsDialog | 652 | ~100 | 85% |
| GlobalSearch | 301 | ~80 | 73% |
| ArtistDetailView | 398 | ~120 | 70% |
| CozyLibraryView | 398 | ~240 | 40% |
| CozyArtistList | 368 | ~80 | 78% |
| AutoMasteringPane | 589 | 0 | 100% |
| **TOTAL** | **2,706** | **~620** | **77%** |

---

## Next Steps After Phase 5

1. **Documentation Update**
   - Update CONSOLIDATION_EXECUTION_SUMMARY.md
   - Update CLAUDE.md with final metrics
   - Archive Phase 5 completion details

2. **Metrics Collection**
   - Final build time
   - Test pass rate
   - Code coverage
   - Module count reduction

3. **Team Communication**
   - Share completion summary
   - Document lessons learned
   - Update component guidelines

4. **Future Maintenance**
   - Monitor for new consolidation opportunities
   - Prevent component size regression
   - Review extraction patterns

---

## References

- **Component Consolidation Roadmap**: [COMPONENT_CONSOLIDATION_ROADMAP.md](./COMPONENT_CONSOLIDATION_ROADMAP.md)
- **Component Patterns**: [COMPONENT_PATTERNS.md](./COMPONENT_PATTERNS.md)
- **Previous Phases Summary**: [CONSOLIDATION_EXECUTION_SUMMARY.md](./CONSOLIDATION_EXECUTION_SUMMARY.md)

---

**Status**: 🎯 Ready for Phase 5A (Week 1)
**Start Date**: [To be scheduled]
**Expected Completion**: 3-4 weeks after start
**Current Effort Invested (Phases 1-4)**: 9-11 hours, 1,031+ lines removed
