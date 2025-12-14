# Phase 5: Test Suite Migration - Implementation Plan

**Date**: December 12, 2025
**Status**: Planning Phase
**Scope**: Update 26+ test files and 10 conftest.py files to support RepositoryFactory

---

## Executive Summary

Phase 5 migrates the test suite to properly support RepositoryFactory dependency injection. Current state:
- ✅ 90+ existing fixtures supporting both LibraryManager and RepositoryFactory patterns
- ✅ 80 dual-mode tests already validating both patterns
- ⚠️ 26 test files still directly instantiating LibraryManager
- ⚠️ Player component tests skipped due to database initialization issues
- ⚠️ Component initialization doesn't pass get_repository_factory getter

**Objective**: Enable all tests to work with refactored components while maintaining backward compatibility.

---

## Current Test Infrastructure

### Fixture Ecosystem (90+ fixtures)

**Main conftest.py (tests/conftest.py)**:
- `library_manager` - LibraryManager with temp DB (26 files use this)
- `repository_factory` - RepositoryFactory with session factory (11 files use this)
- `session_factory` - SQLAlchemy SessionLocal
- `dual_mode_data_source` - Parametrized both patterns (80 dual-mode tests)
- Individual repos: `track_repository`, `album_repository`, etc.
- Audio fixtures: `sine_wave`, `white_noise`, `test_audio_files`

**Backend conftest.py (tests/backend/conftest.py)**:
- `mock_library_manager` - Full mock with all repos
- `mock_repository_factory` - Full mock factory
- `mock_data_source` - Parametrized dual-mode mocks
- `client` - FastAPI TestClient
- `sample_audio` - Test audio data

**Performance/Concurrency/Stress conftest.py**:
- Performance-specific fixtures (timers, benchmarks)
- Thread-safety fixtures (pools, barriers, locks)
- Resource monitoring (memory, CPU)
- Load testing fixtures (large datasets, stress configs)

### Test Statistics

| Category | Count | Using LibraryManager | Using RepositoryFactory | Status |
|----------|-------|----------------------|--------------------------|--------|
| Backend API tests | 53 files | 15 files ⚠️ | Partial | Mixed |
| Integration tests | 11 files | Most ⚠️ | Some ✅ | Partial |
| Unit tests | 28 files | Most ⚠️ | Some ✅ | Partial |
| Performance tests | 10+ files | Some | Some ✅ | Dual-mode |
| Concurrency tests | 8+ files | Some | Some ✅ | Dual-mode |
| Player tests | 2 files | Uses direct init | None | Skipped ⚠️ |

**Total Impact**: 26+ test files need updates to pass `get_repository_factory` properly

---

## Phase 5 Breakdown

### Phase 5A: Foundation Setup (Week 1)

**Goal**: Establish fixtures and add missing RepositoryFactory support to conftest files

#### 5A.1: Update Main conftest.py

**Current**: Has `repository_factory` but may need adjustment for component usage
**Changes Needed**:
- ✅ Verify `repository_factory` fixture returns callable (for dependency injection)
- ✅ Ensure `session_factory` is properly scoped
- ✅ Add fixture documentation for RepositoryFactory pattern
- ✅ Create helper function: `get_repository_factory_callable()`

**Implementation**:
```python
@pytest.fixture
def get_repository_factory_callable(repository_factory):
    """Return a callable that provides RepositoryFactory (for DI pattern)"""
    def _get_factory():
        return repository_factory
    return _get_factory
```

**Files to Update**:
- `/mnt/data/src/matchering/tests/conftest.py`

**Estimated Effort**: 0.5 hours

---

#### 5A.2: Update Backend conftest.py

**Current**: Has mock fixtures but may need RepositoryFactory mock
**Changes Needed**:
- ✅ Add `mock_repository_factory_callable` fixture
- ✅ Ensure all router test mocks include factory callable
- ✅ Update `client` fixture to inject factory into app state

**Implementation**:
```python
@pytest.fixture
def mock_repository_factory_callable():
    """Return callable that provides mocked RepositoryFactory"""
    factory = Mock()
    factory.tracks = Mock()  # Mock all repositories
    factory.albums = Mock()
    # ... etc

    def _get_factory():
        return factory
    return _get_factory

@pytest.fixture
def client(mock_repository_factory_callable):
    # Override app's get_repository_factory with mock
    app.dependency_overrides[get_repository_factory] = mock_repository_factory_callable
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**Files to Update**:
- `/mnt/data/src/matchering/tests/backend/conftest.py`

**Estimated Effort**: 1 hour

---

#### 5A.3: Create Player Component Test Fixtures

**Current**: Player tests are skipped, not integrated with fixtures
**Changes Needed**:
- Create fixtures for QueueController with factory
- Create fixtures for IntegrationManager with factory
- Create fixtures for EnhancedAudioPlayer with factory
- Add to appropriate conftest (probably tests/auralis/player/conftest.py)

**Implementation**:
```python
@pytest.fixture
def queue_controller(get_repository_factory_callable):
    """Create QueueController with RepositoryFactory"""
    return QueueController(get_repository_factory_callable)

@pytest.fixture
def integration_manager(get_repository_factory_callable):
    """Create IntegrationManager with dependencies"""
    playback = PlaybackController()
    file_manager = AudioFileManager()
    queue = QueueController(get_repository_factory_callable)
    processor = RealtimeProcessor()

    return IntegrationManager(
        playback, file_manager, queue, processor,
        get_repository_factory=get_repository_factory_callable
    )

@pytest.fixture
def enhanced_player(get_repository_factory_callable):
    """Create EnhancedAudioPlayer with RepositoryFactory"""
    return EnhancedAudioPlayer(
        config=PlayerConfig(),
        get_repository_factory=get_repository_factory_callable
    )
```

**Files to Create/Update**:
- Create `/mnt/data/src/matchering/tests/auralis/player/conftest.py`

**Estimated Effort**: 1 hour

---

### Phase 5B: Critical Test Updates (Week 2)

**Goal**: Migrate high-priority test files to pass factory callable properly

#### 5B.1: Update Test Files Using LibraryManager

**Files to Update (15 Backend API tests)**:
1. `tests/backend/test_library_api.py` (high priority)
2. `tests/backend/test_playlists_api.py` (high priority)
3. `tests/backend/test_metadata.py` (high priority)
4. `tests/backend/test_cache_operations.py` (medium)
5. `tests/backend/test_file_format_support.py` (medium)
6. `tests/backend/test_database_migrations.py` (medium)
7. `tests/backend/test_concurrent_operations.py` (medium)
8. `tests/backend/test_api_endpoint_integration.py` (medium)
9-15. Other backend tests

**Pattern Change**:
```python
# BEFORE
def test_something(library_manager):
    result = library_manager.get_track(1)
    assert result is not None

# AFTER
def test_something(get_repository_factory_callable):
    factory = get_repository_factory_callable()
    result = factory.tracks.get_by_id(1)
    assert result is not None

# OR (Dual-mode for validation)
@pytest.mark.parametrize("data_source", ["manager", "factory"])
def test_something(data_source, library_manager, get_repository_factory_callable):
    if data_source == "manager":
        result = library_manager.tracks.get_by_id(1)
    else:
        factory = get_repository_factory_callable()
        result = factory.tracks.get_by_id(1)
    assert result is not None
```

**Estimated Effort**: 4 hours (15 files × ~15 min each)

---

#### 5B.2: Update Integration Tests

**Files to Update (4 files)**:
- `tests/integration/test_repositories.py`
- `tests/integration/test_library_integration.py`
- `tests/integration/test_fingerprint_extraction.py`
- `tests/integration/test_e2e_workflows.py`

**Pattern**: Similar to 5B.1, but focus on cross-component workflows

**Estimated Effort**: 2 hours

---

### Phase 5C: Backend/API Test Mocking (Week 2)

**Goal**: Set up proper mocking for router dependency injection

#### 5C.1: Mock Setup for Router Tests

**Current Pattern**:
```python
def test_get_tracks(client, library_manager):
    # client doesn't know about get_repository_factory override
    response = client.get("/api/tracks")
```

**Target Pattern**:
```python
def test_get_tracks(client, mock_repository_factory_callable):
    # client has factory injected via dependency override
    response = client.get("/api/tracks")
    assert response.status_code == 200
```

**Implementation Changes**:
1. Update backend conftest to inject factory into app
2. Create comprehensive mock RepositoryFactory with all repos
3. Pre-populate mock repos with test data
4. Handle fixture composition (app, client, factory all connected)

**Files to Update**:
- `/mnt/data/src/matchering/tests/backend/conftest.py`

**Estimated Effort**: 2 hours

---

### Phase 5D: Performance/Load Tests (Week 3)

**Goal**: Extend dual-mode testing to performance benchmarks

#### 5D.1: Update Performance Tests

**Current**: Some dual-mode support exists
**Target**: All performance tests validate both patterns perform comparably

**Files to Update**:
- `tests/performance/test_library_operations_performance.py`
- `tests/performance/test_latency_benchmarks.py`
- `tests/performance/test_realworld_scenarios_performance.py`

**Pattern**:
```python
@pytest.mark.parametrize("data_source_type", ["manager", "factory"])
def test_track_query_performance(data_source_type, performance_data_source, timer):
    with timer:
        if data_source_type == "manager":
            tracks, total = data_source.get_all_tracks(limit=100)
        else:
            tracks, total = data_source.tracks.get_all(limit=100)

    # Assert performance is acceptable for both patterns
    assert timer.elapsed < 0.1  # 100ms threshold
```

**Estimated Effort**: 1.5 hours

---

### Phase 5E: Player Component Tests (Week 3-4)

**Goal**: Integrate player component tests with fixture ecosystem

#### 5E.1: Refactor Player Tests

**Current**: Tests are skipped due to database initialization
**Target**: Tests use proper fixtures and validate both patterns

**Changes**:
1. Replace `setUp()` with pytest fixtures
2. Inject `get_repository_factory_callable`
3. Remove direct LibraryManager instantiation
4. Create dual-mode tests where applicable

**Files to Update**:
- `tests/auralis/player/test_enhanced_player.py`
- `tests/auralis/player/test_enhanced_player_detailed.py`

**Example Refactor**:
```python
# BEFORE (unittest-style, skipped)
class TestEnhancedPlayer(unittest.TestCase):
    def setUp(self):
        self.manager = LibraryManager(':memory:')  # Direct instantiation
        self.player = EnhancedAudioPlayer(library_manager=self.manager)

    def test_play(self):
        # Uses self.player
        pass

# AFTER (pytest-style)
def test_play(enhanced_player, get_repository_factory_callable):
    """Test player playback functionality"""
    # enhanced_player already has factory injected
    assert enhanced_player.play() == True
```

**Estimated Effort**: 3 hours

---

### Phase 5F: Remaining Tests (Week 4)

**Goal**: Complete migration of all remaining test files

#### 5F.1: Unit Tests

**Files to Update**: ~15 auralis module test files
**Pattern**: Similar to backend tests, update fixtures and assertions

**Estimated Effort**: 3 hours

---

#### 5F.2: Concurrency/Stress Tests

**Files to Update**: ~8 concurrency, 5 stress test files
**Pattern**: Extend dual-mode testing, ensure thread-safe factory callable

**Estimated Effort**: 2 hours

---

## Implementation Order (Priority)

### TIER 1: Foundation (Weeks 1)
1. ✅ Phase 5A.1: Update main conftest.py
2. ✅ Phase 5A.2: Update backend conftest.py
3. ✅ Phase 5A.3: Create player component fixtures

**Outcome**: All conftest files ready, fixtures support both patterns

### TIER 2: High-Impact (Weeks 2)
4. Phase 5B.1: Update 15 backend API tests (high priority)
5. Phase 5B.2: Update 4 integration tests
6. Phase 5C.1: Mock setup for router tests

**Outcome**: All API endpoints properly injected with factory

### TIER 3: Specialized (Weeks 3-4)
7. Phase 5D.1: Update performance tests
8. Phase 5E.1: Refactor player component tests
9. Phase 5F.1: Update unit tests
10. Phase 5F.2: Update concurrency/stress tests

**Outcome**: Full test suite migration complete

---

## Success Criteria

### Phase 5A Success
- ✅ All conftest files have RepositoryFactory fixtures
- ✅ `get_repository_factory_callable` available in all test contexts
- ✅ Player component fixtures created and documented
- ✅ Backward compatibility maintained (library_manager still available)

### Phase 5B Success
- ✅ 15+ backend API tests updated and passing
- ✅ Integration tests working with both patterns
- ✅ Router mocking properly injects factory
- ✅ FastAPI client has factory in dependency overrides

### Phase 5D-F Success
- ✅ All 26+ test files updated to pass factory callable
- ✅ Dual-mode tests validate both patterns work identically
- ✅ Performance tests show comparable results for both patterns
- ✅ Player component tests no longer skipped
- ✅ Full test suite passes with new component signatures

---

## Challenges & Mitigations

### Challenge 1: Circular Fixture Dependencies
**Problem**: IntegrationManager needs QueueController, which needs factory
**Solution**: Use fixture composition instead of direct instantiation in fixtures

### Challenge 2: Mock Setup Complexity
**Problem**: Mocking all 11 repositories for router tests
**Solution**: Create `MockRepositoryFactory` class that auto-mocks all repos

### Challenge 3: Player Test Database Issues
**Problem**: Current player tests fail on database initialization
**Solution**: Use in-memory SQLite via session_factory fixture, set up before player instantiation

### Challenge 4: Test Data Consistency
**Problem**: Tests need consistent track/album data across dual-mode tests
**Solution**: Use shared fixtures that populate both manager and factory identically

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Tests fail after refactoring components | High | Run test suite frequently, catch issues early |
| Player test complexity | Medium | Start with simpler unit tests, progress to integration |
| Mock setup errors | Medium | Create reusable MockRepositoryFactory base class |
| Performance regression | Low | Phase 5D validates both patterns perform similarly |

---

## Rollback Plan

If issues arise:
1. Keep `library_manager` fixture available (backward compatible)
2. Tests can revert to using `library_manager` directly
3. `get_repository_factory_callable` is new, no existing tests depend on it
4. Player tests remain skipped if refactoring incomplete

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 5A: Foundation | 2 hours | 2 hours |
| Phase 5B: High-Priority | 4 hours | 6 hours |
| Phase 5C: Mocking | 2 hours | 8 hours |
| Phase 5D: Performance | 1.5 hours | 9.5 hours |
| Phase 5E: Player Tests | 3 hours | 12.5 hours |
| Phase 5F: Remaining | 5 hours | 17.5 hours |
| **Total** | **~18 hours** | **~18 hours** |

**Accelerated Path** (focus on Phase 5A-5B only): ~6 hours
- Gets all routers and player components working
- Defers performance/stress test optimization

---

## Next Steps After Phase 5

1. **Verify Test Suite**: Run full test suite with new component signatures
2. **Integration Testing**: Validate all components work together
3. **Performance Validation**: Ensure new pattern performs as well as old
4. **Documentation**: Update test documentation for new patterns
5. **CI/CD Integration**: Update pipeline to run new tests

---

## Conclusion

Phase 5 establishes proper fixture support for RepositoryFactory pattern across all test categories. The migration follows a prioritized approach, starting with foundation setup and high-impact API tests, then extending to specialized test categories.

Success criteria focuses on:
1. **All components properly injected** with factory callable
2. **Dual-mode validation** ensuring both patterns work identically
3. **Player tests unblocked** and integrated with fixtures
4. **Full backward compatibility** maintained during transition

