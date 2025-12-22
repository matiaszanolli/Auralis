# Frontend & Integration Test Revamp Strategy

## Executive Summary

**Current State**: 513 test files across frontend (128) and backend (185), with significant quality issues
- **Frontend**: 1,425 total tests, ~76% passing (1,084 passing, 168 failing, 173 skipped)
- **Backend**: 850+ tests with good coverage, but 7 import/module errors blocking some tests
- **Integration**: 11 test files covering end-to-end scenarios

**Goal**: Achieve ≥90% passing rate and establish sustainable test patterns

---

## Current Problems

### Frontend Tests (High Priority)

🔴 **Memory & Async Issues** (Primary Blocker)
- 168 failing tests (11.8% failure rate)
- Root causes:
  1. Missing `act()` wrappers on async state updates
  2. WebSocket subscriptions not cleaned up properly
  3. Provider nesting creating closure issues
  4. Timers/intervals not cleared between tests
  5. Memory leaks from incomplete cleanup

🟡 **Specific Test Files with High Failure Rates**
- `GlobalSearch.test.tsx` - 31/35 failing (88% failure)
- `TrackListView.test.tsx` - 24/42 failing (57% failure)
- `ArtistDetailView.test.tsx` - 17/43 failing (40% failure)
- `useInfiniteScroll.test.ts` - 17/20 failing (85% failure)
- `TrackRow.test.tsx` - 14/33 failing (42% failure)
- `AlbumArt.test.tsx` - 11/11 failing (100% failure)

🟡 **Infrastructure Issues**
- Need 2GB heap to run full test suite (`npm run test:memory`)
- TypeScript types not fully correct for test utilities
- MSW (Mock Service Worker) setup could be optimized
- Vitest configuration may need tuning

### Backend/Integration Tests (Medium Priority)

🟡 **Import Errors** (Blocking 7 test modules)
- `chunk_boundaries` module missing references
- Affects:
  - `test_api_endpoint_integration.py`
  - `test_chunked_processor.py` (and variants)
  - `test_processing_parameters.py`
  - `test_api_integration.py`
  - `test_end_to_end_processing.py`

🟡 **Test Coverage Gaps**
- Some edge cases not covered
- Integration scenarios need expansion
- Performance testing limited

---

## Revamp Strategy

### Phase 1: Fix Frontend Memory & Async Issues (Priority: CRITICAL)

**Goal**: Reduce frontend test failures from 168 (11.8%) to <50 (<3.5%)

#### Step 1.1: Fix High-Failure Test Files (80/128 tests fail)
- `GlobalSearch.test.tsx` → 35 tests need async fixes
- `TrackListView.test.tsx` → 42 tests need async fixes
- `ArtistDetailView.test.tsx` → 43 tests need cleanup
- `useInfiniteScroll.test.ts` → 20 tests need observer mocking
- `TrackRow.test.tsx` → 33 tests need provider cleanup
- `AlbumArt.test.tsx` → 11 tests need lifecycle fixes

**Pattern to Apply**:
```typescript
// ❌ BEFORE (causes failures)
test('loads items', async () => {
  render(<Component />);
  await waitFor(() => {
    expect(screen.getByText('Item')).toBeInTheDocument();
  });
});

// ✅ AFTER (proper async handling)
test('loads items', async () => {
  await act(async () => {
    render(<Component />);
  });
  await act(async () => {
    await waitFor(() => {
      expect(screen.getByText('Item')).toBeInTheDocument();
    });
  });
});
```

#### Step 1.2: Fix WebSocket Cleanup
- Ensure all WebSocket subscriptions cleaned up in `afterEach`
- Add explicit unsubscribe calls
- Test example:
```typescript
afterEach(() => {
  // Unsubscribe from all WebSocket listeners
  if (wsContextValue?.unsubscribe) {
    wsContextValue.unsubscribe('all');
  }
});
```

#### Step 1.3: Fix Provider Nesting
- Simplify nested providers in test setup
- Extract common provider combinations
- Consider provider factory pattern

#### Step 1.4: Fix Timers & Intervals
- Clear all fake timers in `afterEach`
- Use `vi.clearAllTimers()` consistently
- Add timer assertions where needed

**Estimated Impact**: 90+ test failures resolved (11.8% → <1%)

### Phase 2: Fix Backend Import Errors (Priority: HIGH)

**Goal**: Get all 185 test files collecting without errors

#### Step 2.1: Resolve `chunk_boundaries` Module
- Check if module moved/renamed
- Update imports in:
  - `chunked_processor.py`
  - Integration test files
- Create stub if needed for tests

#### Step 2.2: Fix Other Import Issues
- Audit remaining error messages
- Update paths/imports systematically
- Run `pytest --collect-only` to verify

**Estimated Impact**: All test modules should collect cleanly

### Phase 3: Improve Integration Tests (Priority: MEDIUM)

**Goal**: Expand integration test coverage to 20+ files

#### Step 3.1: Add Missing Integration Scenarios
- Player state transitions
- Queue operations
- Library operations with caching
- WebSocket message handling

#### Step 3.2: Create Integration Test Patterns
```python
# Example pattern
class TestPlayerWorkflow:
    def test_load_track_updates_all_state(self, player, library):
        """Verify track load updates player state and UI."""
        track = library.get_first_track()
        player.load(track)
        assert player.current_track == track
        assert player.duration == track.duration
        assert player.is_loaded is True

    def test_play_pause_sequence(self, player):
        """Verify play/pause toggle works."""
        player.load(TEST_TRACK)
        player.play()
        assert player.is_playing is True

        player.pause()
        assert player.is_playing is False
        assert player.position > 0  # Position preserved
```

### Phase 4: Establish Test Quality Standards (Priority: MEDIUM)

**Goal**: Create reusable patterns for future tests

#### Step 4.1: Frontend Test Pattern Guide
- Async/await with act()
- WebSocket subscription cleanup
- Provider nesting best practices
- Memory leak prevention checklist

#### Step 4.2: Backend Test Pattern Guide
- Fixture usage (Phase 5 RepositoryFactory)
- Mocking external dependencies
- Assertion patterns
- Setup/teardown best practices

#### Step 4.3: Integration Test Pattern Guide
- End-to-end workflow patterns
- State verification patterns
- Error scenario patterns
- Performance baseline patterns

---

## Implementation Plan

### Week 1: Frontend Cleanup
| Task | Time | Files |
|------|------|-------|
| Fix GlobalSearch.test.tsx | 2h | 35 tests |
| Fix TrackListView.test.tsx | 2h | 42 tests |
| Fix ArtistDetailView.test.tsx | 1.5h | 43 tests |
| Fix WebSocket cleanup (all files) | 2h | 128 files |
| Fix provider nesting | 1.5h | 15 files |
| **Total** | **9h** | **263 tests** |

### Week 2: Backend Fixes & Integration
| Task | Time | Impact |
|------|------|--------|
| Fix chunk_boundaries imports | 1h | 7 test modules |
| Fix other import errors | 1h | Remaining errors |
| Add integration scenarios | 3h | +10 test files |
| Create test pattern docs | 2h | Future tests |
| **Total** | **7h** | **185+ tests** |

### Week 3: Validation & Documentation
| Task | Time |
|------|------|
| Run full frontend test suite | 1h |
| Run full backend test suite | 1h |
| Verify >90% pass rate | 1h |
| Document new patterns | 2h |
| Create test maintenance guide | 1h |
| **Total** | **6h** |

---

## Success Criteria

### Frontend Tests
- ✅ Pass rate: **≥90%** (up from 76%)
- ✅ No memory warnings in test output
- ✅ All cleanup proper (no resource leaks)
- ✅ Full suite runs in <5 minutes with 2GB heap
- ✅ Pattern guide documented and followed

### Backend/Integration Tests
- ✅ All test modules collect without errors
- ✅ All 850+ backend tests passing
- ✅ 20+ integration test files
- ✅ Coverage of major workflows
- ✅ Consistent error message format

### Documentation
- ✅ Frontend test patterns documented
- ✅ Backend test patterns documented
- ✅ Integration test patterns documented
- ✅ Troubleshooting guide created
- ✅ Maintenance runbook established

---

## Test Metrics to Track

| Metric | Current | Target | How to Measure |
|--------|---------|--------|-----------------|
| Frontend Pass Rate | 76% | ≥90% | `npm run test:memory` |
| Frontend Memory Usage | OOM | <2GB | Monitor during `npm run test:memory` |
| Backend Pass Rate | ~95% | ≥99% | `pytest --tb=short` |
| Integration Coverage | 11 files | 20+ files | Count test files in `tests/integration/` |
| Test Execution Time | ~3-5m | <5m | Time test suite run |
| Flaky Test Rate | Unknown | <1% | Run tests 3x, count inconsistencies |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking working tests | High | Create feature branch, verify before merge |
| Missing fixtures | Medium | Audit fixture usage before refactor |
| Performance regression | Medium | Compare test execution time before/after |
| Type errors in tests | Low | Run `npm run type-check` after changes |

---

## Rollback Plan

All changes are non-functional:
- Pure test improvements, no code changes
- Git history preserved
- Can revert individual files if issues arise
- Keep failing tests documented (git commit message)

---

## Next Steps

1. ✅ Create this strategy document
2. → Launch Phase 1 (Frontend cleanup)
3. → Launch Phase 2 (Backend import fixes)
4. → Create pattern guides
5. → Run validation suite
6. → Document maintenance procedures

