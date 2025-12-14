# Auralis Testing Plan
**Generated:** 2025-10-24
**Current Status:** Test coverage evaluation and comprehensive testing roadmap

## Executive Summary

### Current Test Coverage

**Backend (Python):**
- **Overall Coverage:** 65.5%
- **Total Statements:** 5,569
- **Covered Lines:** 3,648
- **Missing Lines:** 1,921
- **Test Files:** 96 tests across 6 test files
- **Status:** ⚠️ **MODERATE** - Core functionality tested, critical gaps exist

**Frontend (React/TypeScript):**
- **Test Files:** 14 files with 245 tests total
- **Passing:** 72 tests (29.4%)
- **Failing:** 173 tests (70.6%)
- **Status:** ⚠️ **FAILING** - Infrastructure exists but many tests broken

---

## 1. Backend Test Coverage Analysis

### 1.1 Currently Tested Modules (Good Coverage: >70%)

✅ **Well-Tested Areas:**
- Processing API endpoints (100% pass rate, 43 tests)
- Processing Engine (100% pass rate, 19 tests)
- Player State Manager (100% pass rate, 17 tests)
- Queue Management endpoints (100% pass rate, 10 tests)

### 1.2 Critical Untested/Low Coverage Areas (<50%)

❌ **Modules Requiring Immediate Attention:**

| Module | Coverage | Priority | Impact |
|--------|----------|----------|--------|
| `unified_loader.py` | 0.0% | **CRITICAL** | Audio loading failures undetected |
| `preview_creator.py` | 27.3% | HIGH | Preview generation untested |
| `preference_engine.py` | 29.7% | HIGH | User preferences may fail |
| `realtime_adaptive_eq.py` | 30.2% | **CRITICAL** | Core EQ functionality |
| `saver.py` | 33.3% | **CRITICAL** | Audio export may fail silently |
| `enhanced_audio_player.py` | 40.2% | **CRITICAL** | Playback failures |
| `psychoacoustic_eq.py` | 41.9% | HIGH | EQ processing edge cases |
| `realtime_processor.py` | 46.4% | HIGH | Real-time processing bugs |
| `performance_optimizer.py` | 54.8% | MEDIUM | Performance regressions |
| `manager.py` | 59.1% | MEDIUM | Library management bugs |

**Recently Added - Untested:**
- ❌ Albums REST API (`routers/albums.py`) - 0% coverage
- ❌ Artists REST API (`routers/artists.py`) - 0% coverage
- ❌ Metadata editing router (`routers/metadata.py`) - 17/17 tests FAILING
- ❌ Album/Artist repositories pagination - 0% coverage

### 1.3 Known Test Failures

**Metadata Router (17 failures):**
```
tests/backend/test_metadata.py - ALL FAILING
- test_get_editable_fields_success FAILED
- test_get_metadata_success FAILED
- test_update_metadata_success FAILED
- test_batch_update_success FAILED
... (13 more failures)
```

**Root Cause:** Tests outdated after metadata editing implementation

---

## 2. Frontend Test Coverage Analysis

### 2.1 Current State

✅ **Test Infrastructure Exists:**
- **14 test files** with 245 tests
- Vitest + React Testing Library configured
- **72 tests passing (29.4%)**
- **173 tests failing (70.6%)**

**Test Breakdown:**
- ✅ `playlistService.test.ts` - 20 tests PASSING
- ✅ `TEMPLATE.test.tsx` - 15 tests PASSING
- ❌ `usePlayerAPI.test.ts` - ~15 tests FAILING (WebSocket context issues)
- ❌ ~10 other test files - ~158 tests FAILING

**Primary Failure Pattern:**
```
Error: useWebSocketContext must be used within WebSocketProvider
```
Most failures are due to missing WebSocket provider wrapper in tests, not actual logic issues.

### 2.2 Critical Untested Frontend Areas

| Area | Components | Test Status | Priority |
|------|-----------|-------------|----------|
| **Library Views** | CozyLibraryView, CozyAlbumGrid, CozyArtistList | **UNTESTED** | **CRITICAL** |
| **Player Controls** | BottomPlayerBar, EnhancedTrackQueue | **TESTS FAILING** | **CRITICAL** |
| **Album/Artist Detail** | AlbumDetailView, ArtistDetailView | **UNTESTED** | HIGH |
| **Audio Processing** | ProcessingControls, PresetSelector | **UNTESTED** | HIGH |
| **Library Management** | EditMetadataDialog, FolderScanner | **UNTESTED** | MEDIUM |
| **API Services** | playlistService ✅, others untested | **PARTIAL** | HIGH |

---

## 3. Testing Strategy & Roadmap

### Phase 1: Critical Backend Gaps (Week 1-2)

**Goal:** Achieve 80% backend coverage, fix all failures

#### 1.1 Fix Existing Test Failures
- [ ] **Fix metadata router tests** (17 failures)
  - Update mocks for new metadata editing implementation
  - Test file read/write operations
  - Validate batch update logic

- [ ] **Verify core audio processing tests**
  - Ensure all adaptive processing tests pass
  - Test edge cases (empty audio, mono/stereo conversion)

#### 1.2 Test New REST API Endpoints
- [ ] **Albums REST API** (`routers/albums.py`)
  ```python
  # tests/backend/test_albums_api.py
  - test_get_albums_pagination
  - test_get_album_by_id
  - test_get_album_tracks
  - test_album_search
  - test_album_ordering (title, year)
  - test_invalid_album_id
  ```

- [ ] **Artists REST API** (`routers/artists.py`)
  ```python
  # tests/backend/test_artists_api.py
  - test_get_artists_pagination
  - test_get_artist_by_id
  - test_get_artist_tracks
  - test_artist_search
  - test_artist_ordering (name, album_count, track_count)
  - test_invalid_artist_id
  ```

#### 1.3 Test Critical I/O Modules
- [ ] **Audio Loading** (`unified_loader.py` - 0% coverage)
  ```python
  # tests/test_unified_loader.py
  - test_load_wav_file
  - test_load_flac_file
  - test_load_mp3_file
  - test_load_invalid_file
  - test_load_corrupted_file
  - test_load_different_sample_rates
  - test_load_mono_stereo
  ```

- [ ] **Audio Saving** (`saver.py` - 33.3% coverage)
  ```python
  # tests/test_saver.py
  - test_save_wav_16bit
  - test_save_wav_24bit
  - test_save_flac
  - test_save_with_metadata
  - test_save_to_invalid_path
  - test_save_overwrite_protection
  ```

- [ ] **Enhanced Audio Player** (`enhanced_audio_player.py` - 40.2% coverage)
  ```python
  # tests/test_enhanced_audio_player.py
  - test_play_track
  - test_pause_resume
  - test_seek_to_position
  - test_volume_control
  - test_queue_management
  - test_enhancement_toggle
  - test_playback_errors
  - test_format_compatibility
  ```

#### 1.4 Test Repository Pagination
- [ ] **Album Repository** (`repositories/album_repository.py`)
  - test_get_all_with_pagination
  - test_get_all_ordering_by_title
  - test_get_all_ordering_by_year
  - test_search_pagination

- [ ] **Artist Repository** (`repositories/artist_repository.py`)
  - test_get_all_with_pagination
  - test_get_all_ordering_by_name
  - test_get_all_ordering_by_album_count
  - test_search_pagination

**Expected Outcome:** Backend coverage 80%+, all tests passing

---

### Phase 2: Frontend Test Fixes (Week 3)

**Goal:** Fix failing tests, establish working test patterns

#### 2.1 Fix Test Infrastructure Issues
- [ ] **Fix WebSocket provider wrapper** (fixes ~150+ failing tests)
  - Create `test/utils/TestProviders.tsx` wrapper with WebSocketProvider
  - Update all hook tests to use provider wrapper
  - Pattern:
  ```typescript
  // test/utils/TestProviders.tsx
  export const TestProviders = ({ children }) => (
    <WebSocketProvider>
      {children}
    </WebSocketProvider>
  );

  // In tests:
  renderHook(() => usePlayerAPI(), { wrapper: TestProviders });
  ```

- [ ] Add MSW (Mock Service Worker) for API mocking
- [ ] Create test utilities and helpers
- [ ] Setup coverage reporting properly

#### 2.2 Verify Existing Passing Tests
- [x] **playlistService.test.ts** - 20 tests PASSING ✅
- [x] **TEMPLATE.test.tsx** - 15 tests PASSING ✅

#### 2.3 Fix Failing Hook Tests
- [ ] **usePlayerAPI.test.ts** - Fix WebSocket provider wrapper
  - All ~15 tests should pass after provider fix

#### 2.4 Test New REST API Integration (if not covered)
- [ ] Test Albums REST API integration
- [ ] Test Artists REST API integration

**Expected Outcome after Phase 2:** 90%+ frontend tests passing (220+ of 245)
- [ ] **Library Views**
  ```typescript
  // CozyLibraryView.test.tsx
  - test_renders_track_list
  - test_pagination_loads_more
  - test_search_filters_tracks
  - test_view_toggle_grid_list

  // CozyAlbumGrid.test.tsx
  - test_renders_album_grid
  - test_infinite_scroll
  - test_album_click_navigation
  - test_loading_states

  // CozyArtistList.test.tsx
  - test_renders_artist_list
  - test_alphabetical_grouping
  - test_artist_click_navigation
  ```

- [ ] **Player Controls**
  ```typescript
  // BottomPlayerBar.test.tsx
  - test_play_pause_button
  - test_volume_slider
  - test_seek_slider
  - test_track_info_display
  - test_queue_controls
  ```

**Expected Outcome:** 20% frontend coverage, CI/CD ready

---

### Phase 3: Comprehensive Frontend Testing (Week 4-5)

**Goal:** 70% frontend coverage

#### 3.1 Component Testing (Detailed)
- [ ] **Detail Views**
  - AlbumDetailView (track listing, play album, navigation)
  - ArtistDetailView (album listing, track listing)

- [ ] **Processing UI**
  - ProcessingControls (preset selection, settings)
  - JobStatusDisplay (progress, cancellation)

- [ ] **Library Management**
  - EditMetadataDialog (form validation, save/cancel)
  - FolderScanner (scan progress, error handling)
  - SearchBar (debouncing, filtering)

#### 3.2 Integration Testing
- [ ] **User Workflows**
  - Browse library → Play track
  - Search → Filter → Play
  - Process audio → Download result
  - Edit metadata → Save → Verify
  - Create playlist → Add tracks → Play

#### 3.3 Hook Testing
- [ ] `usePlayerAPI.ts` - Player state management
- [ ] `useWebSocket.ts` - WebSocket connection
- [ ] `useInfiniteScroll.ts` - Pagination logic

**Expected Outcome:** 70% frontend coverage

---

### Phase 4: E2E Testing (Week 6)

**Goal:** Critical user flows validated end-to-end

#### 4.1 Setup Playwright/Cypress
- [ ] Configure E2E test framework
- [ ] Setup test database and fixtures
- [ ] Create page object models

#### 4.2 Critical E2E Scenarios
```typescript
// e2e/library-browsing.spec.ts
test('User can browse and play music', async ({ page }) => {
  - Navigate to library
  - Verify tracks load
  - Click play on first track
  - Verify player controls active
  - Verify audio playing (mock)
});

// e2e/audio-processing.spec.ts
test('User can process audio file', async ({ page }) => {
  - Upload audio file
  - Select preset
  - Submit processing job
  - Wait for completion
  - Download result
  - Verify file exists
});

// e2e/metadata-editing.spec.ts
test('User can edit track metadata', async ({ page }) => {
  - Open track context menu
  - Click edit metadata
  - Update title, artist, album
  - Save changes
  - Verify metadata updated
});
```

**Expected Outcome:** Core user flows validated

---

## 4. Testing Best Practices & Guidelines

### 4.1 Backend Testing (Python)

**Test Structure:**
```python
# tests/backend/test_feature.py
import pytest
from fastapi.testclient import TestClient

class TestFeatureName:
    def test_success_case(self, client):
        # Arrange
        ...
        # Act
        response = client.get("/api/endpoint")
        # Assert
        assert response.status_code == 200
        assert response.json()["key"] == expected_value

    def test_error_case(self, client):
        # Test error handling
        ...
```

**Fixtures:**
```python
# tests/conftest.py
@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_library_manager():
    return Mock(spec=LibraryManager)

@pytest.fixture
def sample_audio_file():
    return Path("tests/fixtures/sample.wav")
```

### 4.2 Frontend Testing (React)

**Component Test Structure:**
```typescript
// components/__tests__/Component.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import Component from '../Component';

describe('Component', () => {
  it('renders correctly', () => {
    render(<Component />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('handles user interaction', async () => {
    const handleClick = vi.fn();
    render(<Component onClick={handleClick} />);

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });
});
```

**API Mocking (MSW):**
```typescript
// mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  rest.get('http://localhost:8765/api/library/tracks', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        tracks: [/* mock data */],
        total: 100,
        has_more: true
      })
    );
  }),
];
```

### 4.3 Coverage Targets

| Test Type | Current | Phase 1 | Phase 2 | Phase 3 | Final Goal |
|-----------|---------|---------|---------|---------|------------|
| Backend Unit | 65.5% | 80% | 80% | 85% | **90%** |
| Backend Integration | ~50% | 70% | 80% | 85% | **90%** |
| Frontend Unit | 0% | 0% | 20% | 70% | **80%** |
| Frontend Integration | 0% | 0% | 10% | 50% | **70%** |
| E2E | 0% | 0% | 0% | 30% | **50%** |

---

## 5. CI/CD Integration

### 5.1 GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=auralis --cov=auralis-web/backend --cov-report=xml
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd auralis-web/frontend && npm install
      - run: npm test:coverage
      - uses: codecov/codecov-action@v3
```

### 5.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/backend/ -v
        language: system
        pass_filenames: false
        always_run: true
```

---

## 6. Immediate Action Items (Priority Order)

### Week 1 - Critical Fixes
1. ✅ **Fix metadata router tests** (17 failures) - BLOCKER
2. ✅ **Test Albums/Artists REST APIs** - NEW FEATURES
3. ✅ **Test repository pagination** - DATA INTEGRITY

### Week 2 - Critical Modules
4. ✅ **Test unified_loader.py** (0% → 80%) - CRITICAL
5. ✅ **Test saver.py** (33% → 80%) - CRITICAL
6. ✅ **Test enhanced_audio_player.py** (40% → 80%) - CRITICAL

### Week 3 - Frontend Foundation
7. ✅ **Setup Vitest + Testing Library**
8. ✅ **Test API service layer** (0% → 80%)
9. ✅ **Test CozyLibraryView + CozyAlbumGrid** (critical UI)

### Week 4 - Frontend Coverage
10. ✅ **Test BottomPlayerBar** (player controls)
11. ✅ **Test detail views** (AlbumDetailView, ArtistDetailView)
12. ✅ **Test processing UI**

### Week 5 - Integration
13. ✅ **Frontend integration tests** (user workflows)
14. ✅ **Backend integration tests** (end-to-end API flows)

### Week 6 - E2E
15. ✅ **Setup Playwright**
16. ✅ **Critical E2E scenarios** (play, process, edit)

---

## 7. Testing Tools & Dependencies

### Backend
```txt
# requirements-test.txt
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
httpx==0.25.1
pytest-mock==3.12.0
```

### Frontend
```json
// package.json devDependencies
{
  "@testing-library/react": "^14.0.0",
  "@testing-library/jest-dom": "^6.1.4",
  "@testing-library/user-event": "^14.5.1",
  "vitest": "^1.0.4",
  "@vitest/ui": "^1.0.4",
  "msw": "^2.0.0",
  "happy-dom": "^12.10.3"
}
```

### E2E
```json
{
  "@playwright/test": "^1.40.0"
}
```

---

## 8. Success Metrics

### Quantitative
- Backend coverage: 65.5% → **90%**
- Frontend coverage: 0% → **80%**
- E2E coverage: 0% → **50%** (critical flows)
- Test execution time: <5 minutes (backend + frontend)
- Zero flaky tests (>99% pass rate)

### Qualitative
- All PRs require passing tests
- No production bugs from untested code paths
- Confidence in refactoring (backed by tests)
- Fast feedback loop (<30 seconds for unit tests)

---

## 9. Resources & Documentation

### Learning Resources
- [Pytest Documentation](https://docs.pytest.org/)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Guide](https://vitest.dev/guide/)
- [MSW Documentation](https://mswjs.io/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)

### Project-Specific Guides
- `tests/backend/README.md` - Backend testing guide (to be created)
- `auralis-web/frontend/src/tests/README.md` - Frontend testing guide (to be created)
- `e2e/README.md` - E2E testing guide (to be created)

---

## Appendix A: Current Test Inventory

### Backend Test Files
```
tests/backend/
├── test_main_api.py (52 tests) ✅
├── test_metadata.py (17 tests) ❌ ALL FAILING
├── test_processing_api.py (18 tests) ✅
├── test_processing_engine.py (19 tests) ✅
├── test_queue_endpoints.py (10 tests) ✅
└── test_state_manager.py (17 tests) ✅
```

### Frontend Test Files
```
auralis-web/frontend/src/
└── (No tests exist) ❌
```

---

## Appendix B: Coverage Gaps Summary

### Backend - Zero Coverage
- `routers/albums.py` - Albums REST API
- `routers/artists.py` - Artists REST API
- `unified_loader.py` - Audio file loading
- `preview_creator.py` - Audio preview generation

### Backend - Low Coverage (<50%)
- `realtime_adaptive_eq.py` (30.2%)
- `saver.py` (33.3%)
- `enhanced_audio_player.py` (40.2%)
- `psychoacoustic_eq.py` (41.9%)
- `realtime_processor.py` (46.4%)

### Frontend - Complete Gap
- All 60+ React components (0%)
- All service layer (0%)
- All hooks (0%)
- All utilities (0%)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-24
**Next Review:** After Phase 1 completion
