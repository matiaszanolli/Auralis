# Test Audit and Action Plan

**Date**: October 29, 2025
**Scope**: Backend + Frontend Test Suite
**Goal**: 80%+ coverage, all tests passing

---

## Current Status

### Backend Tests (Python/pytest)

**Overall**: 430 passed, 12 failed, 8 skipped, 18 errors (468 total tests)
**Pass Rate**: 91.9% (430/468)
**Coverage**: ~74% (backend), ~75% (auralis core)

**Breakdown by Category**:

| Category | Status | Count |
|----------|--------|-------|
| ✅ Passing | 430 tests | 91.9% |
| ❌ Failing | 12 tests | 2.6% |
| ⚠️ Skipped | 8 tests | 1.7% |
| 🔴 Errors | 18 tests | 3.8% |

### Frontend Tests (TypeScript/Vitest)

**Overall**: 234 passed, 11 failing (245 total tests)
**Pass Rate**: 95.5% (234/245)
**Coverage**: Unknown (need to run coverage)

**Known Issues**:
- 11 gapless playback component tests failing
- Root cause: Unknown (needs investigation)

---

## Test Failures Analysis

### 1. Similarity API Tests (18 errors)

**File**: `tests/backend/test_similarity_api.py`
**Error**: `fixture 'client' not found`

**Root Cause**: Missing FastAPI test client fixture in conftest.py

**Affected Tests**:
```
test_find_similar_tracks_endpoint
test_find_similar_tracks_with_graph
test_find_similar_tracks_invalid_id
test_compare_tracks_endpoint
test_compare_same_track
test_explain_similarity_endpoint
test_build_graph_endpoint
test_get_graph_stats_endpoint
test_fit_similarity_system_endpoint
test_fit_insufficient_fingerprints
test_negative_limit
test_zero_k_neighbors
test_missing_track_comparison
test_find_similar_response_time
test_graph_query_faster_than_realtime
test_complete_similarity_workflow
test_similarity_consistency
```

**Fix Required**:
Add `client` fixture to `tests/backend/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from auralis-web.backend.main import app

@pytest.fixture
def client():
    """FastAPI test client"""
    with TestClient(app) as client:
        yield client
```

**Priority**: 🔴 **HIGH** (blocks all similarity API tests)

---

### 2. Unified Streaming Tests (12 failures)

**File**: `tests/backend/test_unified_streaming.py`

**Failed Tests**:
```
test_get_metadata_unenhanced
test_get_metadata_enhanced
test_get_metadata_track_not_found
test_get_metadata_default_preset
test_get_metadata_custom_chunk_duration
test_get_chunk_unenhanced_cache_miss
test_get_chunk_unenhanced_cache_hit
test_get_chunk_invalid_track
test_get_chunk_invalid_chunk_index
test_clear_cache
test_large_file_handling
test_zero_duration_track
```

**Needs Investigation**: Run tests with full traceback to see error details

**Priority**: 🟡 **MEDIUM** (unified streaming is Beta.4 feature, should work)

---

### 3. Frontend Gapless Playback Tests (11 failures)

**File**: `auralis-web/frontend/src/components/__tests__/GaplessPlayback.test.tsx`

**Status**: Known issue from CLAUDE.md

**Notes from CLAUDE.md**:
> ⚠️ Known issue: 11 gapless playback tests failing

**Needs Investigation**: Run frontend tests and analyze failures

**Priority**: 🟡 **MEDIUM** (affects playback UI)

---

### 4. Simplified UI Test (1 error)

**File**: `tests/backend/test_simplified_ui.py`

**Error**: Unknown (need full traceback)

**Priority**: 🟢 **LOW** (single test, may be deprecated)

---

## Missing Test Coverage

### 1. .25d Sidecar System (NEW - Beta.6)

**Files Without Tests**:
- `auralis/library/sidecar_manager.py` (342 lines)
- `auralis/library/fingerprint_extractor.py` (updated with .25d support)
- `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py` (NaN handling added)

**Test Files Needed**:
- `tests/auralis/library/test_sidecar_manager.py`
- `tests/auralis/library/test_fingerprint_extractor_with_sidecar.py`
- `tests/auralis/analysis/test_fingerprint_nan_handling.py`

**Test Cases Required**:
- ✅ Sidecar file creation/read/write
- ✅ Sidecar file validation (checksum, timestamp)
- ✅ Cached vs uncached extraction performance
- ✅ Invalid .25d file handling
- ✅ NaN/Inf sanitization in fingerprints
- ✅ Batch extraction with cache statistics

**Priority**: 🔴 **HIGH** (new feature for Beta.6, needs comprehensive testing)

---

### 2. Fingerprint Phase 2 Backend (Beta.5)

**Files Added in Phase 2** (need integration tests):
- `auralis/library/repositories/fingerprint_repository.py`
- `auralis-web/backend/routers/similarity.py`
- `auralis/similarity/engine.py`
- `auralis/similarity/graph.py`
- `auralis/similarity/normalizer.py`

**Existing Test Coverage**:
- Unit tests exist but API tests failing (see #1 above)

**Priority**: 🟡 **MEDIUM** (tests exist, just need fixing)

---

### 3. Fingerprint Phase 2 Frontend (Beta.5)

**Files Added in Phase 2** (need tests):
- `auralis-web/frontend/src/components/SimilarityPanel.tsx`
- `auralis-web/frontend/src/services/similarityService.ts`

**Test Files Needed**:
- `auralis-web/frontend/src/components/__tests__/SimilarityPanel.test.tsx`
- `auralis-web/frontend/src/services/__tests__/similarityService.test.ts`

**Priority**: 🟡 **MEDIUM** (UI component, needs basic tests)

---

## Action Plan

### Phase 1: Fix Existing Test Failures (Week 1)

**Goal**: Get all existing tests passing

**Tasks**:

1. **Fix Similarity API Tests** (2 hours)
   - Add `client` fixture to conftest.py
   - Verify all 18 tests pass
   - Add missing fixtures if needed

2. **Fix Unified Streaming Tests** (4 hours)
   - Run tests with full traceback
   - Identify root cause of 12 failures
   - Fix implementation or update tests
   - Verify all tests pass

3. **Fix Frontend Gapless Playback Tests** (4 hours)
   - Run frontend tests locally
   - Analyze 11 failures
   - Fix component or update tests
   - Verify all tests pass

4. **Fix Simplified UI Test** (1 hour)
   - Run with full traceback
   - Fix or skip if deprecated

**Deliverables**:
- ✅ All backend tests passing (468/468)
- ✅ All frontend tests passing (245/245)
- ✅ 100% pass rate

---

### Phase 2: Add .25d Sidecar Tests (Week 2)

**Goal**: Comprehensive testing for new .25d feature

**Tasks**:

1. **Unit Tests for SidecarManager** (4 hours)
   - Test file creation, read, write, delete
   - Test validation logic
   - Test checksum computation
   - Test bulk operations
   - Target: 90%+ coverage

2. **Integration Tests for FingerprintExtractor** (4 hours)
   - Test cached vs uncached extraction
   - Test cache hit/miss statistics
   - Test invalid .25d file handling
   - Test batch extraction with cache

3. **Unit Tests for NaN Handling** (2 hours)
   - Test NaN/Inf sanitization
   - Test edge cases (all NaN, all Inf)
   - Verify database compatibility

**Deliverables**:
- ✅ `tests/auralis/library/test_sidecar_manager.py` (20+ tests)
- ✅ `tests/auralis/library/test_fingerprint_extractor_sidecar.py` (15+ tests)
- ✅ `tests/auralis/analysis/test_fingerprint_nan.py` (10+ tests)
- ✅ 90%+ coverage for new code

---

### Phase 3: Add Frontend Tests (Week 3)

**Goal**: Test coverage for fingerprint Phase 2 UI

**Tasks**:

1. **SimilarityPanel Component Tests** (4 hours)
   - Test rendering
   - Test user interactions
   - Test API integration
   - Mock API responses

2. **Similarity Service Tests** (2 hours)
   - Test API calls
   - Test error handling
   - Test response parsing

3. **Integration Tests** (2 hours)
   - Test complete similarity workflow
   - Test graph building UI
   - Test find similar UI

**Deliverables**:
- ✅ `SimilarityPanel.test.tsx` (15+ tests)
- ✅ `similarityService.test.ts` (10+ tests)
- ✅ E2E integration tests (5+ tests)

---

### Phase 4: Increase Coverage to 80%+ (Week 4)

**Goal**: Fill coverage gaps in existing code

**Strategy**:
1. Run coverage report to identify gaps
2. Prioritize high-value, low-effort areas
3. Add targeted tests for uncovered branches

**Tasks**:

1. **Backend Coverage Gaps** (8 hours)
   - Run `pytest --cov` to identify gaps
   - Add tests for uncovered code paths
   - Focus on error handling, edge cases

2. **Frontend Coverage Gaps** (8 hours)
   - Run `npm run test:coverage`
   - Add tests for uncovered components
   - Focus on user interactions, API calls

3. **Documentation Update** (2 hours)
   - Update CLAUDE.md with test commands
   - Document test organization
   - Add testing best practices

**Deliverables**:
- ✅ Backend coverage: 80%+ (currently ~74%)
- ✅ Frontend coverage: 80%+ (currently unknown)
- ✅ Updated test documentation

---

## Test Organization Strategy

### Backend Tests (`tests/`)

```
tests/
├── backend/              # Backend API tests
│   ├── test_*.py        # Feature-specific tests
│   └── conftest.py      # Shared fixtures
├── auralis/             # Core library tests
│   ├── library/         # Library management tests
│   │   ├── test_sidecar_manager.py         # NEW
│   │   └── test_fingerprint_extractor.py    # UPDATED
│   ├── analysis/        # Analysis tests
│   │   └── test_fingerprint_nan.py          # NEW
│   └── similarity/      # Similarity system tests
└── validation/          # E2E validation tests
```

### Frontend Tests (`auralis-web/frontend/`)

```
src/
├── components/
│   └── __tests__/
│       ├── SimilarityPanel.test.tsx         # NEW
│       └── GaplessPlayback.test.tsx         # FIX
└── services/
    └── __tests__/
        └── similarityService.test.ts        # NEW
```

---

## Testing Standards

### Backend (pytest)

**File Naming**: `test_<module_name>.py`
**Function Naming**: `test_<function_name>_<scenario>`
**Structure**: Arrange-Act-Assert
**Fixtures**: Use pytest fixtures for common setup
**Coverage Target**: 80%+ per module

**Example**:
```python
def test_sidecar_file_creation(temp_dir, sample_audio):
    """Test .25d file is created with valid content"""
    # Arrange
    manager = SidecarManager()
    audio_path = temp_dir / "test.flac"

    # Act
    success = manager.write(audio_path, {"fingerprint": {...}})

    # Assert
    assert success
    assert manager.exists(audio_path)
    assert manager.is_valid(audio_path)
```

### Frontend (Vitest)

**File Naming**: `<Component>.test.tsx` or `<module>.test.ts`
**Function Naming**: `it('<should do something>')`
**Structure**: Given-When-Then (AAA)
**Mocking**: Use vitest mocks for API calls
**Coverage Target**: 80%+ per component

**Example**:
```typescript
describe('SimilarityPanel', () => {
  it('should render similar tracks when available', async () => {
    // Given
    const mockTracks = [{id: 1, title: 'Track 1'}]
    vi.mocked(findSimilarTracks).mockResolvedValue(mockTracks)

    // When
    render(<SimilarityPanel trackId={1} />)

    // Then
    await waitFor(() => {
      expect(screen.getByText('Track 1')).toBeInTheDocument()
    })
  })
})
```

---

## Success Metrics

### Phase 1: Fix Existing Failures
- ✅ Backend: 468/468 tests passing (100%)
- ✅ Frontend: 245/245 tests passing (100%)
- ✅ Zero skipped tests (investigate and fix or remove)

### Phase 2-3: Add New Tests
- ✅ .25d Sidecar: 45+ new tests
- ✅ Frontend Similarity: 30+ new tests
- ✅ Total tests: 500+ backend, 275+ frontend

### Phase 4: Coverage
- ✅ Backend: 80%+ coverage (up from 74%)
- ✅ Frontend: 80%+ coverage
- ✅ New code: 90%+ coverage

---

## Timeline

**Week 1** (Nov 1-7):
- Fix all existing test failures
- Achieve 100% pass rate

**Week 2** (Nov 8-14):
- Add .25d sidecar tests
- Achieve 90%+ coverage for new code

**Week 3** (Nov 15-21):
- Add frontend similarity tests
- Integration testing

**Week 4** (Nov 22-28):
- Fill coverage gaps
- Documentation updates
- Final review

**Total Duration**: 4 weeks
**Estimated Effort**: ~60 hours

---

## Notes

### Test Execution Commands

**Backend (from root)**:
```bash
# Run all tests
python -m pytest tests/backend/ -v

# Run specific test file
python -m pytest tests/backend/test_similarity_api.py -v

# Run with coverage
python -m pytest tests/backend/ --cov=auralis-web/backend --cov-report=html

# Run core library tests
python -m pytest tests/auralis/ -v
```

**Frontend (from auralis-web/frontend/)**:
```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test file
npm test SimilarityPanel.test.tsx
```

### Continuous Integration

**Current Status**: No CI/CD configured

**Recommendation**: Add GitHub Actions workflow for automated testing on PR

**Workflow**:
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install -r requirements.txt
      - run: pytest tests/backend/ tests/auralis/
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: cd auralis-web/frontend && npm install
      - run: cd auralis-web/frontend && npm test
```

---

## Conclusion

Current test suite is **91.9% passing** (backend) with **74% coverage**. Main issues:

1. **18 similarity API tests** - Missing `client` fixture (easy fix)
2. **12 unified streaming tests** - Need investigation
3. **11 frontend gapless tests** - Known issue, needs fixing
4. **New .25d feature** - No tests yet (45+ tests needed)

**Action**: Execute 4-week plan to achieve 100% pass rate + 80% coverage.

**Priority Order**:
1. 🔴 Fix similarity API tests (2 hours, unblocks 18 tests)
2. 🔴 Add .25d sidecar tests (10 hours, critical for Beta.6)
3. 🟡 Fix unified streaming tests (4 hours)
4. 🟡 Fix gapless playback tests (4 hours)
5. 🟢 Add frontend similarity tests (8 hours)
6. 🟢 Fill coverage gaps (16 hours)

**Est. Total**: 44 hours to complete all phases
