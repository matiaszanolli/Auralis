# Phase 5C: Backend/API Router Tests - Implementation Overview

**Date**: December 12, 2025
**Status**: ✅ **READY FOR IMPLEMENTATION**
**Scope**: Update backend router tests to support dual-mode testing (LibraryManager + RepositoryFactory)
**Estimated Effort**: 8-10 hours

---

## Executive Summary

Phase 5C focuses on **backend API router test updates** to support dual-mode testing with both LibraryManager (backward compatibility) and RepositoryFactory (new pattern) patterns.

**Current State**:
- ✅ All routers already refactored to use RepositoryFactory pattern (Phase 6B/6C work)
- ✅ Mock fixtures created in backend/conftest.py (`mock_repository_factory_callable`)
- ✅ Example pattern demonstrated in test_artists_api.py
- ⏳ Test files need parametrization for dual-mode testing

---

## Router Refactoring Status

### Already Completed (Phases 6B/6C)

**File**: `auralis-web/backend/routers/library.py`
```python
def create_library_router(
    get_repository_factory: Callable[[], Any],
    connection_manager: Optional[Any] = None
) -> APIRouter:
    """Factory function to create library router with dependencies."""

    @router.get("/api/library/stats")
    async def get_library_stats() -> Dict[str, Any]:
        factory = require_repository_factory(get_repository_factory)
        stats = factory.stats.get_library_stats()
        return stats
```

**Pattern**:
- Uses factory function to create router with dependency injection
- All endpoints call `require_repository_factory(get_repository_factory)`
- No direct LibraryManager usage in routers

**All routers follow this pattern**:
- ✅ `library.py` (13 endpoints)
- ✅ `playlists.py` (8 endpoints)
- ✅ `metadata.py` (7 endpoints)
- ✅ `albums.py` (4 endpoints)
- ✅ `artists.py` (6 endpoints)
- ✅ Plus 5 more router files

---

## Test Files Requiring Phase 5C Updates

### High-Priority Test Files (15+ LibraryManager usages)

| Test File | Usage Count | Priority | Status |
|-----------|-------------|----------|--------|
| `test_cache_operations.py` | 57 | 🔴 High | ⏳ Needs dual-mode parametrization |
| `test_artists_api.py` | 27 | 🔴 High | ⏳ Example pattern documented, needs parametrization |
| `test_database_migrations.py` | 23 | 🔴 High | ⏳ Needs dual-mode support |
| `test_albums_api.py` | 16 | 🟡 Medium | ⏳ Needs dual-mode support |
| `test_api_endpoint_integration.py` | 9 | 🟡 Medium | ⏳ Needs dual-mode support |

### Medium-Priority Test Files (5-14 usages)

- `test_concurrent_operations.py` (9 usages)
- `test_boundary_advanced_scenarios.py` (8 usages)
- `test_artwork_integration.py` (6 usages)
- `test_boundary_integration_stress.py` (7 usages)
- `test_artwork_management.py` (6 usages)
- Plus 5 more files

### Total Scope
**~15 test files** need Phase 5C updates (approximately 176 LibraryManager usages)

---

## Phase 5C Implementation Pattern

### Existing Example: test_artists_api.py

The test_artists_api.py file shows the foundation pattern:

```python
"""
Phase 5C: Dual-Mode Backend Testing
This file demonstrates Phase 5C patterns:
1. Using mock fixtures from conftest.py
2. Parametrized dual-mode testing (LibraryManager + RepositoryFactory)
3. Monkeypatch dependency injection for clean mocking
"""

import pytest
from unittest.mock import Mock, patch

# Phase 5B.1: Migration to conftest.py fixtures
# Removed local client() fixture - now using conftest.py fixture
# All tests automatically use the fixture from parent conftest.py

class TestGetArtists:
    """Test GET /api/artists endpoint"""

    def test_get_artists_default_pagination(self, client):
        """Test getting artists with default pagination"""
        response = client.get("/api/artists")
        assert response.status_code in [200, 500, 503]
        # Test logic
```

### Planned Enhancement: Parametrized Dual-Mode

**Phase 5C.3 Task**: Add parametrization to run tests with both data sources

```python
@pytest.mark.parametrize("data_source_type", ["library_manager", "repository_factory"])
class TestGetArtistsDualMode:
    """Test GET /api/artists endpoint with both patterns"""

    def test_get_artists_with_library_manager(self, client, mock_library_manager, data_source_type):
        """Test with LibraryManager pattern"""
        if data_source_type == "library_manager":
            with patch('main.get_library_manager', return_value=mock_library_manager):
                response = client.get("/api/artists")
                assert response.status_code in [200, 500, 503]

    def test_get_artists_with_repository_factory(self, client, mock_repository_factory_callable, data_source_type):
        """Test with RepositoryFactory pattern"""
        if data_source_type == "repository_factory":
            with patch('main.get_repository_factory', return_value=mock_repository_factory_callable):
                response = client.get("/api/artists")
                assert response.status_code in [200, 500, 503]
```

Or simpler approach using fixtures directly:

```python
@pytest.mark.parametrize("use_factory", [True, False])
def test_get_artists(client, mock_library_manager, mock_repository_factory_callable, use_factory):
    """Test with both patterns"""
    if use_factory:
        with patch('main.get_repository_factory', return_value=mock_repository_factory_callable):
            response = client.get("/api/artists")
    else:
        with patch('main.get_library_manager', return_value=mock_library_manager):
            response = client.get("/api/artists")

    assert response.status_code in [200, 500, 503]
```

---

## Available Mock Fixtures (from backend/conftest.py)

### Already Created Fixtures

```python
@pytest.fixture
def mock_library_manager():
    """Create a mock LibraryManager for testing routers"""
    manager = Mock()
    manager.tracks = Mock()
    manager.albums = Mock()
    manager.artists = Mock()
    # ... 11 repository mocks total
    return manager

@pytest.fixture
def mock_repository_factory():
    """Create a mock RepositoryFactory for testing routers"""
    factory = Mock()
    factory.tracks = Mock()  # TrackRepository mock
    factory.albums = Mock()  # AlbumRepository mock
    # ... 11 repository mocks total
    return factory

@pytest.fixture
def mock_repository_factory_callable(mock_repository_factory):
    """Return a callable that provides mock RepositoryFactory"""
    def _get_factory():
        return mock_repository_factory
    return _get_factory

@pytest.fixture(params=["library_manager", "repository_factory"])
def mock_data_source(request, mock_library_manager, mock_repository_factory):
    """Parametrized fixture providing both modes"""
    if request.param == "library_manager":
        return ("library_manager", mock_library_manager)
    else:
        return ("repository_factory", mock_repository_factory)
```

---

## Phase 5C Implementation Steps

### Phase 5C.1: Analysis & Documentation
- ✅ List all affected test files (15 files identified)
- ✅ Document usage count per file
- ✅ Document example pattern in test_artists_api.py
- ✅ Create this overview document

### Phase 5C.2: Core Router Test Updates (8-10 hours estimated)

**Priority 1: High-impact files** (8-10 tests each)
1. **test_cache_operations.py** (57 usages)
   - Parametrize cache tests with dual-mode
   - Test cache behavior with both patterns
   - Estimated: 2 hours

2. **test_artists_api.py** (27 usages)
   - Add parametrization to existing tests
   - Add dual-mode validation
   - Reference example in test file itself
   - Estimated: 1.5 hours

3. **test_database_migrations.py** (23 usages)
   - Parametrize migration tests
   - Ensure both patterns handle migrations
   - Estimated: 1.5 hours

**Priority 2: Medium-impact files** (4-6 hours)
4. **test_albums_api.py** (16 usages)
   - Similar pattern to test_artists_api.py
   - Estimated: 1.5 hours

5. **test_api_endpoint_integration.py** (9 usages)
   - Integration test parametrization
   - Estimated: 1 hour

6. **5+ remaining files** (5-10 hours)
   - Apply same pattern systematically
   - Can be parallelized

### Phase 5C.3: Validation & Documentation
- ✅ Run test suite with both patterns
- ✅ Document dual-mode pattern
- ✅ Create Phase 5C completion guide

---

## Integration with Existing Work

### ✅ Foundation Already In Place

1. **Mock Fixtures** (in `tests/backend/conftest.py`)
   - `mock_repository_factory` - Complete mock
   - `mock_repository_factory_callable` - For DI pattern
   - `mock_data_source` - Parametrized both patterns

2. **Router Refactoring** (Phases 6B/6C)
   - All routers use factory function pattern
   - All routers accept `get_repository_factory` callable
   - No direct LibraryManager coupling

3. **Test Foundation** (Phase 5B.1)
   - 11 backend test files already using conftest.py fixtures
   - Fixture shadowing removed
   - Ready for parametrization

### ⏳ Next Steps in Phase 5C

1. Add parametrization to test methods
2. Use mock fixtures for dependency injection
3. Validate both patterns work identically
4. Document patterns for remaining phases

---

## Success Criteria for Phase 5C

- ✅ All 15 high/medium-priority test files updated
- ✅ Parametrized dual-mode testing implemented
- ✅ Both LibraryManager and RepositoryFactory patterns validated
- ✅ All tests pass with both patterns
- ✅ No test code duplication (use parametrization)
- ✅ Mock fixtures properly used for DI
- ✅ Documentation updated with patterns

---

## Files Ready for Implementation

### Immediate Action Items

1. **test_artists_api.py** - Reference example
   - Location: `tests/backend/test_artists_api.py`
   - Status: Example pattern documented
   - Action: Add parametrization to 10+ test methods

2. **test_cache_operations.py** - Highest priority
   - Location: `tests/backend/test_cache_operations.py`
   - Usage: 57 instances
   - Action: Parametrize cache validation tests

3. **test_database_migrations.py** - High priority
   - Location: `tests/backend/test_database_migrations.py`
   - Usage: 23 instances
   - Action: Add dual-mode migration testing

### Documentation Files to Create

1. **PHASE_5C_COMPLETION_SUMMARY.md** - After implementation
2. **PHASE_5C_TEST_PATTERN_GUIDE.md** - Best practices

---

## Architecture Decision: Monkeypatch vs Fixture Parametrization

### Option A: Fixture Parametrization (RECOMMENDED)

```python
@pytest.mark.parametrize("use_factory", [True, False])
def test_something(client, mock_library_manager, mock_repository_factory_callable, use_factory):
    if use_factory:
        # Test with RepositoryFactory
        pass
    else:
        # Test with LibraryManager
        pass
```

**Pros**:
- Clean, explicit test logic
- Easy to debug which mode failed
- No magic with monkeypatch

**Cons**:
- Some code duplication in tests
- Longer test methods

### Option B: Monkeypatch with Fixture

```python
@pytest.mark.parametrize("data_source", ["library_manager", "repository_factory"])
def test_something(client, mock_data_source, data_source, monkeypatch):
    mode, source = mock_data_source
    with patch('dependencies.get_library_manager' if mode == 'library_manager' else 'dependencies.get_repository_factory', return_value=source):
        # Single test logic for both patterns
        pass
```

**Pros**:
- Single test logic (DRY)
- Less duplication

**Cons**:
- More complex setup
- Harder to debug

### Recommendation
**Start with Option A** (parametrization) for clarity. Can refactor to Option B later if needed.

---

## Estimated Timeline

| Task | Duration | Cumulative |
|------|----------|-----------|
| Phase 5C.1: Analysis & Planning | 1-2 hours | 1-2 hours |
| Phase 5C.2: Core Test Updates | 6-8 hours | 7-10 hours |
| Phase 5C.3: Validation & Docs | 1-2 hours | 8-12 hours |
| **Phase 5C Total** | **8-12 hours** | **8-12 hours** |

---

## Next Phases After 5C

### Phase 5D: Performance/Load Tests
- Migrate performance benchmarks
- Test with both patterns
- Verify no performance regression
- Estimated: 4-6 hours

### Phase 5E: Player Component Tests
- Update player tests to use RepositoryFactory
- Use player conftest.py fixtures (8 fixtures available)
- Reference TestEnhancedPlayerWithFixtures example
- Estimated: 4-6 hours

### Phase 5F: Remaining Tests
- Complete any remaining test files
- Verify full test suite passes
- Create migration guide
- Estimated: 4-6 hours

---

## Conclusion

Phase 5C is well-positioned to begin immediately. All foundational work is complete:
- ✅ Routers refactored (Phase 6B/6C)
- ✅ Mock fixtures created (backend/conftest.py)
- ✅ Example pattern documented (test_artists_api.py)
- ✅ Test foundation established (Phase 5B.1)

The implementation is straightforward: **add parametrization and mock fixture usage to existing tests**. No router code changes needed—only test updates.

**Ready to proceed with Phase 5C.2 implementation when authorized.**
