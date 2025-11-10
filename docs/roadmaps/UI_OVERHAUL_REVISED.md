# UI Overhaul Roadmap - REVISED (Beta 12.1+)

**Date**: November 9, 2025
**Status**: <¯ **ACTIVE**
**Priority**: P0 (Critical for user experience)
**Target**: Beta 13.0 (Q1 2026)

---

## Context & Lessons Learned

### What We've Learned
From Betas 9-12, we've learned:

1. **Incremental is better than big-bang**: Small, tested releases beat massive rewrites
2. **Fix root causes, not symptoms**: Chunking issues stem from player architecture
3. **Design system first**: Having tokens/primitives ready makes UI work faster
4. **Test early, test often**: Frontend bugs are expensive to fix after deployment
5. **Performance matters**: Users notice 100ms delays in audio playback

### Current State (Beta 12.0)
- **56 TypeScript components** (down from 92 in Beta 9)
- **Design system exists**: Tokens, primitives, animations ready
- **Player works**: UnifiedWebMAudioPlayer functional but needs polish
- **Critical bugs fixed**: Async issues, keyboard shortcuts, preprocessing speed

### User Pain Points
1. **Chunking transitions**: 15s/10s overlap implemented but no crossfade yet
2. **Player UI**: Functional but not polished (no smooth animations)
3. **Component duplication**: Still have multiple similar components
4. **Inconsistent styling**: Not all components use design tokens

---

## Revised Goals

### Primary Goal
**Build a professional music player UI incrementally**, shipping improvements in small batches.

###Success Criteria
1.  **Incremental releases** - Ship every 1-2 weeks, not 6 weeks
2.  **Maintain functionality** - No regressions in existing features
3.  **Use design system** - All new/updated components use tokens
4.  **Test coverage** - 80%+ frontend test coverage for new components
5.  **Performance budget** - <100ms UI response time, 60fps animations

---

## Phase 1: Player Core (Beta 12.1) - 1 Week

**Goal**: Fix the player bar to be production-ready with smooth playback

### Week 1: Player Bar v2
**Target**: Beta 12.1 release

**Tasks**:
1. **Audit BottomPlayerBarUnified** (current: 320 lines)
   - Identify what works vs. needs replacement
   - Check design token usage
   - List missing features

2. **Build new PlayerBar component** using design system
   - Clean layout: [Album Art] [Track Info] [Controls] [Volume] [Queue]
   - Use primitives: Button, IconButton, Slider from design-system/
   - Smooth seek bar with proper chunk handling (15s/10s model)
   - Time display with duration

3. **Implement crossfade logic** (THIS FIXES CHUNKING ISSUES)
   - 5-second crossfade between chunks using overlap
   - Smooth volume transitions
   - No audio gaps or stutters

4. **Polish interactions**
   - Hover states on controls
   - Animated play/pause icon transition
   - Volume slider with visual feedback
   - Keyboard shortcuts integration (space, arrows)

5. **Test thoroughly**
   - Manual playback testing (skip, seek, pause, resume)
   - Crossfade quality check
   - Multiple track transitions
   - Edge cases (1-second tracks, 2-hour tracks)

**Deliverable**: Professional player bar with crossfades working

**Success Metrics**:
- Zero audio gaps during chunk transitions
- < 50ms UI response to button clicks
- Smooth 60fps animations
- 80%+ test coverage

---

## Phase 2: Library Polish (Beta 12.2) - 1 Week

**Goal**: Make library browsing fast and beautiful

### Week 2: Library & Navigation
**Target**: Beta 12.2 release

**Tasks**:
1. **Refactor CozyLibraryView** (current: 407 lines)
   - Already well-structured with hooks
   - Add design token usage
   - Improve album grid layout
   - Better loading states (skeleton screens)

2. **Optimize performance**
   - Virtual scrolling for large libraries (10k+ tracks)
   - Lazy-load album artwork
   - Debounced search (300ms)
   - Pagination improvements

3. **Add micro-interactions**
   - Album card hover effect (scale 1.05, shadow)
   - Smooth transitions between views
   - Loading animations
   - Empty state improvements

4. **Navigation polish**
   - Sidebar active states
   - Smooth view transitions
   - Search bar improvements

**Deliverable**: Fast, responsive library browsing

**Success Metrics**:
- < 100ms search response
- Smooth 60fps scrolling
- < 2s initial library load for 1000 tracks

---

## Phase 3: Audio Controls (Beta 12.3) - 1 Week

**Goal**: Professional audio mastering controls

### Week 3: Right Panel Redesign
**Target**: Beta 12.3 release

**Tasks**:
1. **Auto-mastering toggle** - Prominent, clear on/off
2. **Preset selector** - Visual cards instead of dropdown
3. **Parameter sliders** - Smooth, precise controls with design tokens
4. **Processing feedback** - Refined ProcessingToast with 36.6x RT display

**Deliverable**: Professional audio controls

---

## Phase 4: Component Cleanup (Beta 12.4) - 1 Week

**Goal**: Delete duplicates, consolidate components

### Week 4: Consolidation
**Target**: Beta 12.4 release

**Tasks**:
1. **Delete unused components** (identify with grep + manual check)
2. **Merge duplicates** (e.g., multiple visualizers ’ one configurable component)
3. **Migrate to design tokens** - Find hardcoded colors/spacing, replace with tokens
4. **Update tests** - Ensure test coverage maintained

**Deliverable**: Cleaner codebase, <45 components

**Target Reduction**: 56 ’ 40 components (29% reduction)

---

## Phase 5: Final Polish (Beta 13.0) - 2 Weeks

**Goal**: Ship production-ready UI

### Weeks 5-6: Polish & Testing
**Target**: Beta 13.0 release

**Tasks**:
1. **Animation polish**
   - Page transitions
   - Loading states
   - Toast notifications
   - Modal animations

2. **Error states**
   - Empty library onboarding
   - Network error recovery
   - Graceful degradation

3. **Accessibility**
   - Keyboard navigation
   - Focus indicators
   - ARIA labels
   - Screen reader support

4. **Performance audit**
   - Lighthouse score 90+
   - Bundle size optimization
   - Code splitting
   - Lazy loading

5. **User testing**
   - Internal dogfooding
   - Beta user feedback
   - Bug bash session

**Deliverable**: Production-ready Beta 13.0

---

## Implementation Strategy

### Incremental Approach
1. **1 week sprints** with shippable releases
2. **Feature flags** for experimental features
3. **A/B testing** for major UI changes
4. **Rollback plan** for each release

### Design System Usage
```typescript
// L OLD - Hardcoded values
<Box sx={{
  backgroundColor: '#1a1f3a',
  padding: '16px',
  borderRadius: '8px'
}}>

//  NEW - Design tokens
import { tokens } from '@/design-system/tokens';

<Box sx={{
  backgroundColor: tokens.colors.bg.secondary,
  padding: tokens.spacing.md,
  borderRadius: tokens.borderRadius.md
}}>
```

### Component Architecture
```typescript
// Follow this pattern for ALL new components:

import { tokens } from '@/design-system/tokens';
import { Button, IconButton } from '@/design-system/primitives';

export function MyComponent() {
  return (
    <Container>
      {/* Use primitives, not MUI directly */}
      <Button variant="primary">Action</Button>

      {/* Use tokens, not hardcoded values */}
      <Box sx={{ gap: tokens.spacing.sm }}>
        {/* Component content */}
      </Box>
    </Container>
  );
}
```

### Testing Requirements
Every new/updated component must have:
1. **Unit tests** - Component logic
2. **Interaction tests** - User actions (click, hover, keyboard)
3. **Visual regression tests** - Screenshots (future)
4. **Accessibility tests** - ARIA, keyboard navigation

---

## Risk Mitigation

### High-Risk Areas
1. **Player Bar Rewrite** - Critical functionality, thorough testing required
2. **Crossfade Implementation** - Audio quality must be perfect
3. **Performance Regressions** - Monitor bundle size, render times

### Mitigation Strategies
1. **Feature flags** - Roll out changes gradually
2. **Canary releases** - Test with small user group first
3. **Automated testing** - Prevent regressions
4. **Performance monitoring** - Track metrics in production

---

## Success Metrics (Beta 13.0)

### Quantitative
-  **Component count**: 56 ’ 40 (29% reduction)
-  **Design token adoption**: 100% of components
-  **Test coverage**: 80%+ frontend
-  **Performance**: Lighthouse 90+, 60fps animations
-  **Bundle size**: <1MB gzipped

### Qualitative
-  **User feedback**: "Professional UI"
-  **Zero audio gaps**: Perfect crossfades
-  **Fast interactions**: <100ms response
-  **Smooth animations**: 60fps throughout

---

## Timeline

| Phase | Duration | Target Release | Key Deliverable |
|-------|----------|----------------|-----------------|
| Phase 1 | 1 week | Beta 12.1 | Player Bar v2 + Crossfades |
| Phase 2 | 1 week | Beta 12.2 | Library Polish |
| Phase 3 | 1 week | Beta 12.3 | Audio Controls |
| Phase 4 | 1 week | Beta 12.4 | Component Cleanup |
| Phase 5 | 2 weeks | Beta 13.0 | Final Polish |
| **Total** | **6 weeks** | **Q1 2026** | **Production UI** |

**Start Date**: November 10, 2025
**Target Completion**: December 22, 2025

---

## Next Steps (This Week)

### Immediate Actions
1.  Create revised roadmap (this document)
2.  Audit current BottomPlayerBarUnified component
3.  Design new PlayerBar component architecture
4.  Implement crossfade logic in UnifiedWebMAudioPlayer
5.  Build PlayerBar v2 using design system
6.  Test crossfades thoroughly
7.  Ship Beta 12.1

### Questions to Answer
- Should we keep BottomPlayerBarUnified or start fresh?
- How to handle queue display (separate modal vs. slide-up panel)?
- Crossfade curve (linear, logarithmic, or custom)?
- Feature flag for new player bar (gradual rollout)?

---

## Appendix: Component Audit

### Current Components (56 total)
```
Components to KEEP (refactor to use design tokens):
- BottomPlayerBarUnified (320 lines) - Core player
- CozyLibraryView (407 lines) - Library browsing
- ProcessingToast - Status notifications
- Sidebar - Navigation
- TrackQueue - Queue display

Components to DELETE (unused/duplicate):
- [To be identified in Phase 4]

Components to MERGE:
- [To be identified in Phase 4]
```

### Design System Status
 **Complete**:
- tokens.ts - Design tokens
- Button, IconButton, Card, Slider, Input, Badge, Modal, Tooltip primitives
- Animation utilities structure

 **Missing**:
- Dropdown/Select component
- Progress bar component
- Tabs component
- Accordion component

---

**Last Updated**: November 9, 2025
**Owner**: Auralis Team
**Status**: ACTIVE - Phase 1 starting this week
