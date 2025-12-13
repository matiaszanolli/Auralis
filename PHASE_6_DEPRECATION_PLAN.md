# Phase 6: LibraryManager Deprecation Plan

**Date**: December 12, 2025
**Status**: 🚀 **READY TO IMPLEMENT**
**Foundation**: Phases 5A-5D prove RepositoryFactory equivalence
**Decision**: **OPTION B - MINIMAL FACADE** (recommended)

---

## Executive Summary

Based on Phase 5A-5D validation (134+ tests, proven parity), we can now proceed with LibraryManager deprecation. This plan recommends **Option B: Minimal Facade Wrapper** as the safest path to production.

**Timeline**: 2-3 weeks focused work
**Risk Level**: Low (RepositoryFactory already proven equivalent)
**Blocking**: Nothing - ready to start immediately

---

## Deprecation Decision: Option B (Minimal Facade)

### Why Option B Over Option A?

| Aspect | Option A (Removal) | Option B (Facade) |
|---|---|---|
| **Risk** | High - removes backward compat | Low - maintains compat layer |
| **Migration Timeline** | 4-6 weeks | 2-3 weeks |
| **User Impact** | Breaking change | Transparent upgrade |
| **Revert Ability** | Difficult | Easy (just keep facade) |
| **Testing** | All new code paths | Thin wrapper, proven underneath |
| **Production Confidence** | Months of validation needed | Weeks (RepositoryFactory already proven) |

### Phase 6 Implementation: Minimal Facade

LibraryManager becomes a **thin wrapper over RepositoryFactory**:

```python
# auralis/library/manager.py - DEPRECATED but functional

class LibraryManager:
    """
    DEPRECATED: Use RepositoryFactory directly.

    This class is maintained for backward compatibility.
    All operations delegate to RepositoryFactory.

    Migration guide: See PHASE_6_DEPRECATION_PLAN.md
    """

    def __init__(self, database_path: str = ":memory:"):
        """Initialize manager (deprecated)."""
        warnings.warn(
            "LibraryManager is deprecated. Use RepositoryFactory instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._factory = RepositoryFactory(self.SessionLocal)

    # Delegate to factory
    @property
    def tracks(self) -> TrackRepository:
        return self._factory.tracks

    @property
    def albums(self) -> AlbumRepository:
        return self._factory.albums

    # ... other repository properties

    # Convenience methods that wrap factory operations
    def add_track(self, track_info: Dict) -> Optional[Track]:
        """Convenience method - delegates to tracks.add()"""
        return self.tracks.add(track_info)

    def search_tracks(self, query: str):
        """Convenience method - delegates to tracks.search()"""
        return self.tracks.search(query)

    # ... other convenience methods
```

---

## Phase 6 Breakdown

### Phase 6A: Facade Implementation (1 week)

**Goal**: Convert LibraryManager to thin wrapper

**Tasks**:
1. Refactor `manager.py` to delegate to RepositoryFactory
2. Add deprecation warnings to all public methods
3. Maintain all convenience methods (add_track, search_tracks, etc.)
4. Create migration guide for users
5. Update documentation

**Validation**:
- ✅ All Phase 5 tests still pass (80+ tests with both patterns)
- ✅ Backward compatibility verified
- ✅ No new test failures

**Files Modified**:
- `auralis/library/manager.py` (refactor, ~200 lines)
- Add migration guide document
- Update docstrings with deprecation notices

### Phase 6B: Router Refactoring (1 week)

**Goal**: Migrate routers to use RepositoryFactory directly

**Current State**:
- 41 router usages of LibraryManager
- 8 router files need updates
- Dependency injection already in place

**Files by Priority**:
1. `routers/library.py` (13 usages) - HIGH
2. `routers/playlists.py` (8 usages) - HIGH
3. `routers/metadata.py` (7 usages) - MEDIUM
4. `routers/albums.py` (4 usages) - MEDIUM
5. `routers/artists.py` (3 usages) - LOW
6. Others (6 usages) - LOW

**Pattern**:
```python
# Before (uses manager)
@router.get("/api/tracks")
async def get_tracks(limit: int = 50):
    manager = require_library_manager(get_library_manager)
    tracks, total = manager.tracks.get_all(limit=limit)
    return {"tracks": tracks, "total": total}

# After (uses factory)
@router.get("/api/tracks")
async def get_tracks(limit: int = 50):
    factory = require_repository_factory(get_repository_factory)
    tracks, total = factory.tracks.get_all(limit=limit)
    return {"tracks": tracks, "total": total}
```

**Validation**:
- ✅ All API tests still pass (Phase 5C: 48 tests)
- ✅ Backend health checks pass
- ✅ WebSocket integration works

### Phase 6C: Player Components (3-4 days)

**Goal**: Update player components to use RepositoryFactory

**Components**:
1. `player/queue_controller.py` - Use factory for queue operations
2. `player/integration_manager.py` - Use factory for integration
3. `player/enhanced_audio_player.py` - Use factory for playback state

**Pattern**: Accept RepositoryFactory in constructor instead of LibraryManager

```python
# Before
class QueueController:
    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager

# After
class QueueController:
    def __init__(self, repository_factory: RepositoryFactory):
        self.factory = repository_factory
```

**Validation**:
- ✅ Player tests pass
- ✅ Playback still works end-to-end
- ✅ Queue management functional

### Phase 6D: Documentation & Cleanup (3-4 days)

**Goal**: Document deprecation, create migration guide

**Deliverables**:
1. **Migration Guide**: How to upgrade from LibraryManager to RepositoryFactory
2. **Deprecation Notice**: Clear notice in release notes
3. **API Documentation**: Updated to show RepositoryFactory
4. **Code Examples**: Updated all examples to use factory pattern
5. **Changelog**: Document the deprecation timeline

**Migration Guide Sections**:
- Why deprecate (RepositoryFactory advantages)
- How to migrate (code examples)
- Timeline (when removed completely)
- FAQ (common questions)
- Support (contact for help)

---

## Deprecation Timeline

### Phase 6 (Current - 2-3 weeks)
- LibraryManager becomes thin facade
- Deprecation warnings added
- All routers updated to use RepositoryFactory
- Player components updated
- Migration guide published

### Version 1.2 (1-2 months later)
- LibraryManager deprecated but functional
- Release notes prominently feature deprecation notice
- Migration guide available in documentation
- Users can upgrade with warnings only

### Version 2.0 (3-6 months later)
- **OPTION**: Complete removal of LibraryManager
- **OR**: Keep facade indefinitely for compatibility

---

## Risk Mitigation

### Risk 1: Backward Compatibility Breaking
**Mitigation**: Minimal Facade keeps all public APIs
**Validation**: Phase 5 tests cover both patterns
**Rollback**: Easy - just revert to previous version

### Risk 2: Player Component Failures
**Mitigation**: Update components gradually, test each
**Validation**: Player integration tests pass
**Rollback**: Easy - components already structured for injection

### Risk 3: Third-party Code Breaking
**Mitigation**: Deprecation warnings give clear upgrade path
**Documentation**: Comprehensive migration guide
**Timeline**: 6+ months before actual removal

### Risk 4: Performance Regression
**Mitigation**: Phase 5D proved RepositoryFactory parity
**Validation**: All benchmarks pass
**Monitoring**: Performance tracking after deployment

---

## Success Criteria

### Phase 6A (Facade)
- ✅ LibraryManager delegates to RepositoryFactory
- ✅ All public methods maintained
- ✅ Deprecation warnings present
- ✅ Phase 5 tests still pass (80+ tests)

### Phase 6B (Routers)
- ✅ All 8 router files refactored
- ✅ Dependency injection working
- ✅ API tests pass (Phase 5C: 48 tests)
- ✅ No new test failures

### Phase 6C (Components)
- ✅ Player components accept RepositoryFactory
- ✅ Queue management works
- ✅ Playback integration functional
- ✅ Player tests pass

### Phase 6D (Documentation)
- ✅ Migration guide published
- ✅ Deprecation notice visible
- ✅ Examples updated
- ✅ Changelog documented

### Overall Success
- ✅ Full test suite passes (850+ tests)
- ✅ Zero deprecation errors in CI
- ✅ Performance benchmarks maintained
- ✅ User upgrade path clear

---

## Implementation Sequence

### Week 1: Foundation
1. **Phase 6A.1** (2-3 days): Refactor manager.py to facade
   - Create RepositoryFactory delegate pattern
   - Add deprecation warnings
   - Ensure all convenience methods work

2. **Phase 6A.2** (1-2 days): Validation
   - Run all Phase 5 tests
   - Verify backward compatibility
   - Test with real code paths

### Week 2: Infrastructure
3. **Phase 6B.1** (3-4 days): Migrate routers
   - Update 8 router files
   - Refactor 41 usages
   - Update dependency injection

4. **Phase 6B.2** (1 day): Validation
   - Run API tests (Phase 5C)
   - Verify endpoints work
   - Check WebSocket integration

### Week 3: Components & Documentation
5. **Phase 6C** (2-3 days): Update player components
   - Refactor 3 player files
   - Update dependency injection
   - Validate player integration

6. **Phase 6D** (2-3 days): Documentation
   - Write migration guide
   - Update deprecation notices
   - Create changelog entry
   - Publish to documentation site

---

## Testing Strategy

### Unit Tests
```bash
# Run Phase 5 tests to validate facade
python -m pytest tests/ -m "phase5c or phase5d" -v

# Run player tests
python -m pytest tests/auralis/player/ -v

# Run router tests
python -m pytest tests/backend/ -v
```

### Integration Tests
```bash
# Full backend test suite
python -m pytest tests/backend/ -m "not slow" -v

# API endpoint tests
python -m pytest tests/backend/test_*_api.py -v

# End-to-end playback
python -m pytest tests/integration/ -v
```

### Validation
```bash
# Full test suite
python -m pytest tests/ -m "not slow" -v

# Should show:
# - All 850+ tests passing
# - Zero deprecation errors in stderr
# - Performance benchmarks within threshold
```

---

## Communication Plan

### Before Implementation
- [ ] Team meeting to discuss deprecation strategy
- [ ] GitHub issue for tracking progress
- [ ] Milestone created for Phase 6

### During Implementation
- [ ] Commit messages reference Phase 6 progress
- [ ] Pull requests include deprecation context
- [ ] Review cycle includes deprecation check

### After Implementation
- [ ] Release notes highlight deprecation
- [ ] Migration guide published on website
- [ ] Deprecation warnings visible in logs
- [ ] FAQ created for common migration questions

### Long-term
- [ ] Deprecation period: 6+ months
- [ ] Removal decision: v2.0 or never
- [ ] Community feedback: GitHub discussions

---

## Critical Files to Modify

### Phase 6A (Facade)
- `auralis/library/manager.py` - Convert to thin wrapper
- Add: `MIGRATION_GUIDE.md` - User-facing migration documentation

### Phase 6B (Routers)
- `auralis-web/backend/routers/library.py` (13 usages)
- `auralis-web/backend/routers/playlists.py` (8 usages)
- `auralis-web/backend/routers/metadata.py` (7 usages)
- `auralis-web/backend/routers/albums.py` (4 usages)
- `auralis-web/backend/routers/artists.py` (3 usages)
- `auralis-web/backend/routers/similarity.py` (2 usages)
- `auralis-web/backend/routers/artwork.py` (2 usages)
- `auralis-web/backend/routers/webm_streaming.py` (2 usages)

### Phase 6C (Components)
- `auralis/player/queue_controller.py`
- `auralis/player/integration_manager.py`
- `auralis/player/enhanced_audio_player.py`

### Phase 6D (Documentation)
- `MIGRATION_GUIDE.md` - Migration steps and examples
- `DEPRECATION_NOTICE.md` - User-facing deprecation notice
- Update: `README.md` - Point to migration guide
- Update: API documentation - Show RepositoryFactory examples

---

## Recommendations

### Approach
**Go with Option B (Minimal Facade)** because:
1. ✅ Zero risk of breaking changes
2. ✅ Smooth user upgrade path
3. ✅ Can remove anytime later if needed
4. ✅ All Phase 5 validation applies
5. ✅ Familiar pattern to users

### Timeline
**Start Phase 6 immediately** because:
1. ✅ Phase 5A-5D prove RepositoryFactory equivalence
2. ✅ No blockers remaining
3. ✅ Risk is well-mitigated
4. ✅ User benefit (clear deprecation path) is high

### Next Decision
**Phase 5E is now optional**:
- Phase 6 doesn't depend on Phase 5E completion
- Can do Phase 5E in parallel or later
- Focus on Phase 6 for maximum impact

---

## Conclusion

Phase 6 transforms the codebase from "dual pattern support" (Phases 5A-5D) to "RepositoryFactory primary with LibraryManager deprecated." This is a safe, user-friendly transition that:

✅ Removes technical debt gradually
✅ Maintains backward compatibility
✅ Provides clear upgrade path
✅ Can be completed in 2-3 weeks
✅ Has zero blocking dependencies

**Proceed with Phase 6 implementation immediately after Phase 5A-5D approval.**

---

**Document Status**: Implementation Ready
**Risk Level**: Low
**Dependencies**: None - ready to start now
