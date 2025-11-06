# Auralis Master Roadmap

**Last Updated**: November 6, 2025
**Current Version**: Beta 9.0
**Status**: Active Development

---

## Overview

Auralis is in **extended beta phase** with focus on stability, polish, and user experience before 1.0 release.

**Versioning Strategy** (agreed Nov 5, 2025):
- **Beta X.0** = Major releases (new features, architecture changes)
- **Beta X.1, X.2, ...** = Minor releases (bug fixes, polish, small improvements)
- **Beta 10.0** = Next major (UI overhaul)
- **1.0** = Production release (when ready, not rushed)

---

## Current Status (Beta 9.0)

### ✅ Completed (Production Quality)
- **Audio Engine**: 52.8x real-time processing, Numba JIT optimized
- **Streaming**: Unified MSE + Multi-Tier Buffer (Beta 4)
- **Fingerprints**: 25D audio fingerprint system (Beta 8)
- **Interactions**: Drag-drop, batch operations (Beta 6)
- **Cache**: Centralized fingerprint cache (Beta 9.0)
- **Progress**: Fixed chunk duration sync (Beta 9.0)

### ⚠️ Known Issues (Beta 9.0)
- **UI Quality**: "Bootstrap clone" feel, needs complete overhaul
- **Component Bloat**: 92 components, 46k lines (too many duplicates)
- **Preset Buffering**: 2-5s pause when switching (optimization ongoing)
- **Keyboard Shortcuts**: Disabled due to circular dependency

---

## Immediate Priorities (Beta 9.1 - 9.x)

### Beta 9.1 (Bug Fixes & Polish) - Week 1

**Focus**: Stabilize Beta 9.0, minor improvements

**Tasks**:
- [ ] Re-enable keyboard shortcuts (fix circular dependency)
- [ ] Wire real-time processing stats to ProcessingToast
- [ ] Improve preset switching speed (2-5s → <2s)
- [ ] Fix any critical bugs reported by users

**Release Target**: 1 week from Beta 9.0

---

## Major Milestone: Beta 10.0 (UI Overhaul)

### 🎯 Goal: Professional UI Redesign

**Status**: 🎯 **PLANNING PHASE**
**Priority**: P0 (Blocks production quality perception)
**Timeline**: 6 weeks (5 weeks development + 1 week testing)

### Planning Documents
- **[UI_OVERHAUL_PLAN.md](UI_OVERHAUL_PLAN.md)** - Complete 5-week implementation plan
- **[UI_DESIGN_GUIDELINES.md](../guides/UI_DESIGN_GUIDELINES.md)** - **MANDATORY** design rules

### Overview

**Problem**:
- 92 components, 46k lines of React code
- Multiple duplicate implementations (AudioPlayer, EnhancedAudioPlayer, MagicalMusicPlayer...)
- Bootstrap-clone feel, inconsistent patterns
- Technical debt from rapid feature additions

**Solution**:
- **Reduce to ~45 components** (50% reduction)
- **~20k lines of code** (56% reduction)
- **Establish design system** (prevents future bloat)
- **Professional polish** (animations, micro-interactions)
- **Maintain all functionality** (no feature loss)

### 5-Week Plan

#### Week 1: Design System Foundation
- Create design tokens (colors, spacing, typography)
- Build 8 primitive components (Button, Card, Slider, etc.)
- Animation utilities (spring physics, transitions)

**Deliverable**: Design system ready for use

#### Week 2: Core Player UI
- Rebuild BottomPlayerBar v2
- Professional playback controls
- Smooth seek bar with hover preview
- Animated play/pause button

**Deliverable**: Professional player bar

#### Week 3: Library & Navigation
- Simplified library view (grid + list)
- Fast filtering/search
- Clean sidebar navigation
- Album/artist views with hero headers

**Deliverable**: Fast, clean library experience

#### Week 4: Auto-Mastering UI
- Right panel redesign
- Visual preset cards (not dropdown)
- Professional parameter controls
- Real-time visualization

**Deliverable**: Professional audio controls

#### Week 5: Polish & Details
- Micro-interactions and animations
- Error states, empty states
- Accessibility (keyboard nav, focus indicators)
- Testing and bug fixes

**Deliverable**: Production-ready UI

### Success Criteria
- ✅ < 50 total components
- ✅ < 25k lines of code
- ✅ Zero duplicate components
- ✅ Zero console errors
- ✅ Smooth 60fps scrolling
- ✅ Professional visual polish

### Release Target
**Beta 10.0**: 6 weeks from start (early December 2025)

---

## Design System Rules (MANDATORY)

### 📋 New UI Development Rules

**All new UI code MUST follow [UI_DESIGN_GUIDELINES.md](../guides/UI_DESIGN_GUIDELINES.md).**

Key rules:
1. ✅ **One Component Rule** - Only one component per purpose
2. ✅ **No "Enhanced" Versions** - Refactor, don't duplicate
3. ✅ **Design Tokens Only** - No hardcoded values
4. ✅ **< 300 Lines** - Extract if component exceeds
5. ✅ **Performance Budget** - 60fps, virtual scrolling for long lists

**Violations will be rejected in PR review.**

---

## Future Milestones (Post-Beta 10.0)

### Beta 11.0: Smart Features (Planned)

**Focus**: Leverage 25D fingerprint system

**Features**:
- Smart playlists based on acoustic similarity
- "Find similar tracks" feature
- Cross-genre discovery
- Automatic playlist generation

**Timeline**: 3-4 weeks after Beta 10.0

### Beta 12.0: Enhanced Queue (Planned)

**Focus**: Advanced queue management

**Features**:
- Save queue state
- Queue history
- Suggested next tracks (based on fingerprints)
- Queue shuffle improvements

**Timeline**: 2-3 weeks after Beta 11.0

### Beta 13.0: Performance Optimizations (Planned)

**Focus**: Speed and efficiency

**Features**:
- Faster preset switching (<1s)
- Improved library scanning (1000+ files/sec)
- Memory optimization
- Battery usage optimization (laptop/mobile)

**Timeline**: 2-3 weeks after Beta 12.0

---

## Path to 1.0 (Production Release)

### Requirements for 1.0
- ✅ Professional UI (Beta 10.0)
- ✅ Zero known crashes
- ✅ Zero data loss bugs
- ✅ Complete documentation
- ✅ User onboarding flow
- ✅ Auto-update system working
- ✅ 80%+ test coverage
- ✅ 3+ months of beta stability

### Estimated Timeline
**1.0 Release**: Q1 2026 (3-4 months from now)

---

## Dependencies & Technical Debt

### Technical Debt (Tracked)

| Issue | Priority | Target |
|-------|----------|--------|
| UI Component Bloat | P0 | Beta 10.0 |
| Keyboard Shortcuts | P1 | Beta 9.1 |
| Preset Buffering | P1 | Beta 9.1 |
| Test Coverage Gaps | P2 | Beta 11.0 |
| Frontend Test Failures | P2 | Beta 11.0 |

### Performance Targets

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Audio Processing | 52.8x RT | 50x+ RT | ✅ Met |
| Library Scan | 740 files/s | 1000 files/s | 📈 Improving |
| First Paint | ~600ms | <500ms | 📈 Close |
| Time to Interactive | ~1.2s | <1s | 📈 Close |
| Bundle Size | 790KB | <1MB | ✅ Met |

---

## Communication & Documentation

### Release Notes
- **Major releases** (X.0): Full release notes with features, fixes, testing guide
- **Minor releases** (X.1, X.2): Brief release notes with bug fixes

### Documentation Updates
- Keep [CLAUDE.md](../../CLAUDE.md) in sync with latest architecture
- Update guides in [docs/guides/](../guides/) as features evolve
- Maintain session docs in [docs/sessions/](../sessions/) for major work

### User Communication
- Announce releases on GitHub Discussions
- Maintain CHANGELOG.md with all changes
- Thank beta testers and acknowledge feedback

---

## Risk Management

### Identified Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| UI overhaul breaks features | High | Parallel development, feature flags |
| Timeline slips | Medium | Strict scope control, no feature creep |
| User resistance to new UI | Medium | Beta 9.5 preview, gather feedback |
| Performance regression | High | Performance budget, continuous monitoring |

### Rollback Plans

**Beta 10.0 Rollback**:
- Feature flag to toggle between old/new UI
- Can revert to Beta 9.x UI if critical issues
- Keep old components until Beta 10.0 is stable

---

## Success Metrics

### Engagement Metrics (Target for 1.0)
- Daily active users: Track growth
- Session duration: Target 30+ min average
- Crash-free sessions: 99.5%+
- User retention (7-day): 60%+

### Quality Metrics
- Zero known crashes: ✅
- Zero data loss bugs: ✅
- Test coverage: > 80%
- Code review approval: 100%

### Performance Metrics
- Audio processing: > 50x real-time
- First paint: < 500ms
- Time to interactive: < 1s
- 60fps scrolling: All views

---

## Team Practices

### Code Review
- **All PRs require review** before merge
- **UI PRs must follow design guidelines** (strict)
- Performance testing for optimization PRs
- Accessibility testing for UI changes

### Testing
- Unit tests: All new features
- Integration tests: Critical flows
- E2E tests: User journeys
- Manual testing: Beta releases

### Release Process
1. Feature branch → PR → Review → Merge
2. Version bump in package.json
3. Update RELEASE_NOTES
4. Build packages (AppImage + DEB)
5. Generate checksums
6. Create Git tag
7. Create GitHub release
8. Announce in Discussions

---

## Long-Term Vision (Post-1.0)

### Potential Features (Not Committed)
- Windows/macOS versions (currently Linux-only)
- Mobile app (Android/iOS)
- Cloud sync (playlists, settings)
- Social features (share playlists, collaborate)
- Plugin system (custom presets, visualizations)
- Streaming service integration (Spotify, Tidal)

**Note**: These are ideas, not commitments. Focus is on 1.0 quality first.

---

## Key Documents

### Planning & Design
- **[UI_OVERHAUL_PLAN.md](UI_OVERHAUL_PLAN.md)** - Beta 10.0 implementation plan
- **[UI_DESIGN_GUIDELINES.md](../guides/UI_DESIGN_GUIDELINES.md)** - Mandatory UI rules
- **[BETA3_ROADMAP.md](BETA3_ROADMAP.md)** - Original MSE streaming plan (completed)

### Technical Guides
- **[CLAUDE.md](../../CLAUDE.md)** - Project overview and architecture
- **[PERFORMANCE_OPTIMIZATION_QUICK_START.md](../../PERFORMANCE_OPTIMIZATION_QUICK_START.md)** - Performance optimization guide
- **[LARGE_LIBRARY_OPTIMIZATION.md](../completed/LARGE_LIBRARY_OPTIMIZATION.md)** - Large library support

### Release Documentation
- **[CHANGELOG.md](../../CHANGELOG.md)** - Version history
- **[RELEASE_NOTES_BETA9.0.md](../../RELEASE_NOTES_BETA9.0.md)** - Latest release notes

---

## Questions & Feedback

### For Development Questions
- See [CLAUDE.md](../../CLAUDE.md) for architecture and development guide
- See [UI_DESIGN_GUIDELINES.md](../guides/UI_DESIGN_GUIDELINES.md) for UI rules

### For User Feedback
- GitHub Issues: https://github.com/matiaszanolli/Auralis/issues
- GitHub Discussions: https://github.com/matiaszanolli/Auralis/discussions

---

**Last Updated**: November 6, 2025
**Next Review**: Beta 10.0 planning kickoff (after Beta 9.1 release)
**Status**: Active, evolving with project needs
