# Auralis Test Implementation Roadmap

**Version:** 1.0.0
**Last Updated:** November 6, 2024
**Target Completion:** Beta 10.0 (Q1 2025)

---

## Executive Summary

### Current State (Nov 6, 2024)

**Critical Reality Check:**

```
📊 Source Code:
- Backend Python: 248 files
- Frontend TypeScript: 95 files (non-test)
- Total: 343 source files

🧪 Test Coverage:
- Backend Python: 76 test files, 200 test functions
- Frontend TypeScript: 21 test files, 245 tests
- Total: 97 test files, ~445 tests

📉 Test-to-Code Ratio:
- Backend: 0.31 (76 test files / 248 source files)
- Frontend: 0.22 (21 test files / 95 source files)
- Industry standard: 1.0-2.0 (equal or more tests than source)

❌ VERDICT: Severely undertested (3-6x below industry standard)
```

### Test Quality Analysis

**Type Distribution** (Backend only, 200 tests):
- **Unit tests**: 117 (58.5%)
- **Mocked tests**: 76 (38.0%) - ⚠️ Many test mocks, not behavior
- **Integration tests**: 5 (2.5%) - ❌ Critically low
- **E2E tests**: 2 (1.0%) - ❌ Almost non-existent

**Missing Test Markers:**
- No `@pytest.mark.unit` markers
- No `@pytest.mark.audio` markers
- No `@pytest.mark.performance` markers
- Limited organization and categorization

### Critical Files Without Tests

**Backend (0% test coverage):**
- ❌ `auralis-web/backend/main.py` (737 lines) - FastAPI app entry point
- ❌ `auralis-web/backend/routers/player.py` (1,002 lines) - Player API
- ❌ `auralis-web/backend/routers/library.py` (522 lines) - Library API
- ❌ `auralis/core/hybrid_processor.py` (409 lines) - Core audio processing
- ❌ `auralis/library/manager.py` (270 lines) - Library management

**Result:** ~2,900 lines of **critical path code** with **zero tests**

### The Overlap Bug: Why This Matters

**Bug:** `OVERLAP_DURATION = 3s` with `CHUNK_DURATION = 10s` caused audio gaps
**Coverage:** 100% line coverage ✅
**Bug Detection:** 0% - **test never failed** ❌

**Missing Tests That Would Have Caught It:**

```python
# Test #1: Invariant validation (would have failed immediately)
def test_overlap_is_appropriate_for_chunk_duration():
    """MISSING: Would have prevented overlap bug"""
    assert OVERLAP_DURATION < CHUNK_DURATION / 2, \
        f"Overlap {OVERLAP_DURATION}s too large for {CHUNK_DURATION}s chunks"

# Test #2: Chunk continuity validation (would have detected gaps)
def test_chunks_cover_entire_duration_no_gaps():
    """MISSING: Would have detected 3s duplicate audio"""
    chunks = [processor.process_chunk(i) for i in range(processor.total_chunks)]
    concatenated = np.concatenate(chunks)
    assert len(concatenated) == len(original_audio), "Gap/overlap detected"
```

**Lesson:** **Coverage ≠ Quality**. We need tests that validate **behavior**, not just execute lines.

---

## Goals and Targets

### Phase 1: Foundation (Beta 9.1 - December 2024)

**Target:** Add 300 critical-path tests (645 total tests)

**Priorities:**
1. ✅ **Invariant tests** for all chunked/paginated systems
2. ✅ **Integration tests** for major workflows
3. ✅ **Boundary tests** for edge cases
4. ✅ Test organization with proper markers

**Deliverables:**
- 100 invariant tests (chunk boundaries, pagination, audio continuity)
- 50 integration tests (E2E workflows)
- 150 boundary/edge case tests
- Test marker system implementation
- CI/CD quality gates

### Phase 2: Comprehensive Coverage (Beta 10.0 - Q1 2025)

**Target:** 1,200 total tests (3x current)

**Priorities:**
1. ✅ Property-based tests with hypothesis
2. ✅ Mutation testing (>80% mutation score)
3. ✅ Performance regression tests
4. ✅ Frontend integration tests

**Deliverables:**
- 85% backend coverage with quality validation
- 80% frontend coverage
- Mutation score >80%
- Performance benchmarks in CI

### Phase 3: Test-Driven Development (Beta 11.0 - Q2 2025)

**Target:** 2,500+ tests (test-to-code ratio 1.0+)

**Priorities:**
1. ✅ Comprehensive E2E test suite
2. ✅ Visual regression testing (frontend)
3. ✅ Load/stress testing
4. ✅ TDD for all new features

---

## Phase 1 Implementation Plan (Beta 9.1)

### Week 1: Critical Path Invariants (100 tests)

#### Chunked Processing (30 tests)

**File:** `tests/backend/test_chunked_processor_invariants.py`

```python
class TestChunkedProcessorInvariants:
    """Invariant tests for chunked audio processing"""

    def test_overlap_is_smaller_than_half_chunk_duration(self):
        """Invariant: Overlap < CHUNK_DURATION / 2 to prevent duplicate audio"""
        assert OVERLAP_DURATION < CHUNK_DURATION / 2

    def test_chunks_cover_entire_duration_exactly_once(self):
        """Invariant: Sum of chunk durations = original duration"""
        # ... (30 tests total)
```

**Tests to add:**
1. Overlap duration validation (5 tests)
2. Chunk boundary continuity (10 tests)
3. Duration preservation (5 tests)
4. Level transition smoothness (5 tests)
5. Sample alignment (5 tests)

#### Library Pagination (30 tests)

**File:** `tests/backend/test_library_pagination_invariants.py`

**Tests to add:**
1. Pagination returns all items exactly once (10 tests)
2. Offset boundaries (10 tests)
3. Empty/single-item edge cases (5 tests)
4. Limit validation (5 tests)

#### Audio Processing (20 tests)

**File:** `tests/auralis/test_hybrid_processor_invariants.py`

**Tests to add:**
1. Sample count preservation (5 tests)
2. Sample rate preservation (5 tests)
3. LUFS target tolerance (5 tests)
4. Dynamic range limits (5 tests)

#### Library Management (20 tests)

**File:** `tests/backend/test_library_manager_invariants.py`

**Tests to add:**
1. Duplicate track prevention (5 tests)
2. Foreign key integrity (5 tests)
3. Scan idempotency (5 tests)
4. Cache consistency (5 tests)

### Week 2: Integration Tests (50 tests)

#### End-to-End Workflows (30 tests)

**File:** `tests/integration/test_e2e_workflows.py`

1. **Add track to library** (5 tests)
   - Scan folder → extract metadata → add to database → verify retrieval

2. **Play track with enhancement** (5 tests)
   - Load track → apply preset → stream chunks → verify continuity

3. **Switch presets mid-playback** (5 tests)
   - Play track → switch preset → verify seamless transition

4. **Paginate large library** (5 tests)
   - Scan 1,000 tracks → paginate retrieval → verify completeness

5. **Search and filter** (5 tests)
   - Search by artist → filter by genre → verify results

6. **Artwork management** (5 tests)
   - Extract artwork → download from API → delete → verify state

#### API Integration (20 tests)

**File:** `tests/integration/test_api_workflows.py`

1. **Player API** (7 tests)
   - Play → pause → seek → next → previous → queue → volume

2. **Library API** (7 tests)
   - GET tracks → POST scan → PUT metadata → DELETE track

3. **Enhancement API** (6 tests)
   - GET presets → POST apply → GET progress → WebSocket updates

### Week 3: Boundary Tests (150 tests)

#### Edge Cases for Every Component

**Files:** `tests/boundaries/test_*_boundaries.py`

**Chunked Processing** (30 tests):
- Chunk at exact 0s, 10s, 20s boundaries
- Last chunk shorter than CHUNK_DURATION
- Single chunk (duration < CHUNK_DURATION)
- Very long audio (>1 hour, many chunks)

**Pagination** (30 tests):
- Empty result set (0 items)
- Single item
- Exact page boundary (50 items with limit=50)
- Last page partial (47 items on last page)
- Offset beyond total count

**Audio Processing** (30 tests):
- Minimum duration (0.1s)
- Maximum duration (2 hours)
- Silent audio (all zeros)
- Maximum amplitude (clipping)
- Different sample rates (44.1k, 48k, 96k, 192k)

**Library Operations** (30 tests):
- Empty library
- Single track
- 10,000 tracks (performance test)
- Invalid file paths
- Corrupt audio files

**String Inputs** (30 tests):
- Empty strings
- Very long strings (1000+ chars)
- Special characters, Unicode, emojis
- SQL injection attempts (security)
- Path traversal attempts (security)

### Week 4: Test Organization & CI (Setup)

#### Test Markers Implementation

**File:** `pytest.ini` (updated)

```ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (moderate speed)
    e2e: End-to-end tests (slow)
    invariant: Invariant property tests
    boundary: Boundary condition tests
    audio: Audio processing tests
    library: Library management tests
    player: Player tests
    api: API endpoint tests
    performance: Performance benchmarks
    slow: Slow tests (>1s)
    security: Security tests
```

#### Refactor Existing Tests

Add markers to 200 existing tests:
```bash
# Script to auto-add markers
python scripts/add_test_markers.py
```

#### CI Pipeline Updates

**File:** `.github/workflows/test.yml` (enhanced)

```yaml
jobs:
  test-fast:
    # Unit + invariant tests (<30s total)
    run: pytest -m "unit or invariant" --maxfail=5

  test-integration:
    # Integration tests (~2-3 min)
    run: pytest -m integration --maxfail=3

  test-e2e:
    # E2E tests (~5-10 min)
    run: pytest -m e2e --maxfail=1

  test-coverage:
    # Coverage report with quality validation
    run: |
      pytest --cov=auralis --cov=auralis-web/backend --cov-report=xml
      python scripts/validate_test_quality.py  # Custom quality checks
```

---

## Phase 2 Implementation Plan (Beta 10.0)

### Month 1: Property-Based Testing (200 tests)

#### Install hypothesis

```bash
pip install hypothesis pytest-hypothesis
```

#### Audio Processing Properties (100 tests)

**File:** `tests/properties/test_audio_properties.py`

```python
from hypothesis import given, strategies as st

@given(
    duration=st.floats(min_value=1.0, max_value=600.0),
    sample_rate=st.sampled_from([44100, 48000, 96000])
)
def test_processing_preserves_duration(duration, sample_rate):
    """Property: Processing never changes duration"""
    audio = generate_sine_wave(duration, sample_rate)
    processed = processor.process(audio, sample_rate)
    assert len(processed) == len(audio)
```

**Properties to test:**
1. Duration preservation (10 tests)
2. Sample count preservation (10 tests)
3. LUFS target achievement (10 tests)
4. Dynamic range limits (10 tests)
5. No clipping at any intensity (10 tests)
6. Chunk concatenation = original (10 tests)
7. Stereo channel independence (10 tests)
8. Phase coherence (10 tests)
9. Frequency response (10 tests)
10. Transient preservation (10 tests)

#### Pagination Properties (50 tests)

**File:** `tests/properties/test_pagination_properties.py`

**Properties:**
1. All items returned exactly once (10 tests)
2. Order consistency (10 tests)
3. Count accuracy (10 tests)
4. Boundary handling (10 tests)
5. Performance consistency (10 tests)

#### String Input Properties (50 tests)

**File:** `tests/properties/test_input_properties.py`

**Properties:**
1. No crashes on any valid string (10 tests)
2. SQL injection prevention (10 tests)
3. Path traversal prevention (10 tests)
4. Unicode handling (10 tests)
5. Length limits (10 tests)

### Month 2: Mutation Testing (Setup + 100 tests)

#### Install mutpy

```bash
pip install mutpy
```

#### Run Mutation Analysis

```bash
mutpy --target auralis --unit-test tests/ --runner pytest --report-html /tmp/mutpy-report
```

#### Fix Low-Quality Tests

**Goal:** >80% mutation score

**Common issues to fix:**
1. Tests with meaningless assertions (`assert x is not None`)
2. Tests that don't verify behavior (only execution)
3. Over-mocked tests (everything is mocked)
4. Tests that pass when code breaks

**Add 100 tests** to improve mutation score.

### Month 3: Frontend Integration (200 tests)

#### Component Integration Tests (100 tests)

**File:** `auralis-web/frontend/src/tests/integration/`

**Tests:**
1. Library view → album grid → album detail (20 tests)
2. Track search → filter → play (20 tests)
3. Player controls → seek → volume → queue (20 tests)
4. Enhancement panel → preset selection → apply (20 tests)
5. Artwork management → extract → download → display (20 tests)

#### API Integration with MSW (100 tests)

**File:** `auralis-web/frontend/src/tests/api-integration/`

**Setup:**
```bash
cd auralis-web/frontend
npm install msw --save-dev
```

**Tests:**
1. Mock API responses (20 tests)
2. Error handling (20 tests)
3. Loading states (20 tests)
4. Pagination (20 tests)
5. Real-time updates (WebSocket) (20 tests)

### Month 4: Performance Tests (100 tests)

#### Performance Regression Suite

**File:** `tests/performance/test_regression.py`

**Tests:**
1. Processing speed (20 tests)
   - Track real-time factor for various durations
   - Alert if drops below 10x real-time

2. Memory usage (20 tests)
   - Track memory during processing
   - Alert if exceeds 500MB for 5-minute track

3. Library operations (20 tests)
   - Scan performance (tracks/second)
   - Query performance (latency targets)

4. API response times (20 tests)
   - Track endpoint latency
   - Alert if exceeds targets

5. Frontend rendering (20 tests)
   - Track component render times
   - Alert if FPS drops below 60

---

## Phase 3 Implementation Plan (Beta 11.0)

### Month 1-2: Comprehensive E2E Suite (300 tests)

#### User Scenarios (100 tests)

**Full user workflows:**
1. First-time setup (10 tests)
2. Library management (20 tests)
3. Playback scenarios (20 tests)
4. Playlist management (15 tests)
5. Queue operations (15 tests)
6. Enhancement workflows (20 tests)

#### Cross-Platform Testing (100 tests)

**Platforms:**
- Linux (50 tests)
- Windows (25 tests)
- macOS (25 tests)

#### Browser Testing (100 tests)

**Browsers:**
- Chrome (40 tests)
- Firefox (30 tests)
- Safari (20 tests)
- Edge (10 tests)

### Month 3-4: Visual Regression & Load Testing (200 tests)

#### Visual Regression (100 tests)

**Tool:** Playwright with screenshot comparison

**Components:**
- Album grid layouts (20 tests)
- Player bar states (20 tests)
- Enhancement panel (20 tests)
- Library views (20 tests)
- Theme variations (20 tests)

#### Load & Stress Testing (100 tests)

**Scenarios:**
1. 10,000 concurrent WebSocket connections (10 tests)
2. 50,000 track library (20 tests)
3. Sustained playback (24 hours) (10 tests)
4. Rapid preset switching (20 tests)
5. Concurrent users (40 tests)

---

## Test Implementation Schedule

### Phase 1: Beta 9.1 (4 weeks)

| Week | Focus | Tests Added | Total Tests |
|------|-------|-------------|-------------|
| 1 | Critical invariants | 100 | 545 |
| 2 | Integration workflows | 50 | 595 |
| 3 | Boundary conditions | 150 | 745 |
| 4 | Organization & CI | 0 | 745 |

**Milestone:** 745 tests, organized with markers, CI quality gates

### Phase 2: Beta 10.0 (4 months)

| Month | Focus | Tests Added | Total Tests |
|-------|-------|-------------|-------------|
| 1 | Property-based | 200 | 945 |
| 2 | Mutation testing | 100 | 1,045 |
| 3 | Frontend integration | 200 | 1,245 |
| 4 | Performance | 100 | 1,345 |

**Milestone:** 1,345 tests, >80% mutation score, performance baselines

### Phase 3: Beta 11.0 (4 months)

| Period | Focus | Tests Added | Total Tests |
|--------|-------|-------------|-------------|
| Month 1-2 | E2E suite | 300 | 1,645 |
| Month 3-4 | Visual/Load | 200 | 1,845 |
| Ongoing | TDD for new features | 655 | 2,500 |

**Milestone:** 2,500+ tests, comprehensive coverage, TDD workflow

---

## Testing Tools & Infrastructure

### Backend Testing

**Core Tools:**
```bash
pip install pytest pytest-cov pytest-asyncio pytest-xdist
pip install hypothesis      # Property-based testing
pip install mutpy          # Mutation testing
pip install pytest-benchmark  # Performance benchmarks
```

**Optional:**
```bash
pip install pytest-mock    # Better mocking
pip install pytest-timeout  # Test timeouts
pip install pytest-randomly  # Randomize test order
```

### Frontend Testing

**Core Tools:**
```bash
cd auralis-web/frontend
npm install --save-dev vitest @testing-library/react @testing-library/user-event
npm install --save-dev msw  # API mocking
npm install --save-dev @vitest/coverage-v8  # Coverage
```

**Optional:**
```bash
npm install --save-dev playwright  # E2E testing
npm install --save-dev @playwright/test  # Playwright test runner
```

### CI/CD Integration

**GitHub Actions Workflow:**

```yaml
name: Comprehensive Test Suite

on: [push, pull_request]

jobs:
  test-fast:
    name: Fast Tests (Unit + Invariant)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run fast tests
        run: pytest -m "unit or invariant" -n auto --maxfail=5
    timeout-minutes: 5

  test-integration:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: test-fast
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest -m integration --maxfail=3
    timeout-minutes: 10

  test-e2e:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    needs: test-integration
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E tests
        run: pytest -m e2e --maxfail=1
    timeout-minutes: 20

  test-mutation:
    name: Mutation Testing (Weekly)
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v3
      - name: Run mutation tests
        run: mutpy --target auralis --unit-test tests/ --runner pytest
    timeout-minutes: 60

  quality-gates:
    name: Quality Gates
    runs-on: ubuntu-latest
    needs: [test-fast, test-integration, test-e2e]
    steps:
      - name: Check coverage
        run: |
          pytest --cov --cov-report=xml --cov-fail-under=85
      - name: Validate test quality
        run: python scripts/validate_test_quality.py
```

---

## Success Metrics

### Coverage Metrics

**Target (Beta 10.0):**
- Backend: ≥85% line coverage
- Frontend: ≥80% line coverage
- Critical paths: 100% coverage

**Measurement:**
```bash
# Backend
pytest --cov=auralis --cov=auralis-web/backend --cov-report=term-missing

# Frontend
cd auralis-web/frontend && npm run test:coverage
```

### Quality Metrics

**Target (Beta 10.0):**
- Mutation score: ≥80%
- Defect detection rate: ≥90%
- Test specificity: ≥85%

**Measurement:**
```bash
# Mutation testing
mutpy --target auralis --unit-test tests/ --runner pytest

# Custom quality script
python scripts/validate_test_quality.py
```

### Performance Metrics

**Target (Beta 10.0):**
- Test suite execution: <10 minutes (CI)
- Fast tests (unit + invariant): <2 minutes
- Integration tests: <5 minutes
- E2E tests: <10 minutes

**Measurement:**
```bash
pytest --durations=20  # Show slowest 20 tests
```

### Test-to-Code Ratio

**Target (Beta 11.0):**
- Backend: ≥1.0 (equal or more test files than source files)
- Frontend: ≥1.0
- Overall: ≥1.0

**Current (Nov 6, 2024):**
- Backend: 0.31 (76 / 248)
- Frontend: 0.22 (21 / 95)
- **Gap:** Need 3x more tests to reach parity

---

## Quality Validation Script

### Custom Test Quality Checker

**File:** `scripts/validate_test_quality.py`

```python
#!/usr/bin/env python3
"""
Validate test quality beyond coverage percentage.

Checks:
1. No tests with only `assert True` or `assert x is not None`
2. Integration tests cover major workflows
3. Boundary tests exist for paginated/chunked systems
4. Performance tests have baseline assertions
"""

import re
import sys
from pathlib import Path

def check_meaningless_assertions(test_file):
    """Find tests with meaningless assertions"""
    with open(test_file, 'r') as f:
        content = f.read()

    # Pattern: assert something is not None
    if re.search(r'assert \w+ is not None', content):
        return f"⚠️  {test_file}: Contains 'is not None' assertion"

    # Pattern: assert True
    if re.search(r'assert True', content):
        return f"⚠️  {test_file}: Contains 'assert True'"

    return None

def check_invariant_coverage():
    """Ensure critical invariants are tested"""
    required_invariants = [
        ("chunk overlap", "test_overlap_is_appropriate_for_chunk_duration"),
        ("chunk continuity", "test_chunks_cover_entire_duration"),
        ("pagination completeness", "test_pagination_returns_all_items_exactly_once"),
        ("duration preservation", "test_processing_preserves_duration"),
    ]

    missing = []
    for name, test_name in required_invariants:
        if not any(Path("tests").rglob(f"*{test_name}*")):
            missing.append(name)

    if missing:
        print(f"❌ Missing invariant tests: {', '.join(missing)}")
        return False
    return True

def main():
    print("=== TEST QUALITY VALIDATION ===\n")

    issues = []

    # Check all test files
    for test_file in Path("tests").rglob("test_*.py"):
        issue = check_meaningless_assertions(test_file)
        if issue:
            issues.append(issue)

    # Check invariant coverage
    if not check_invariant_coverage():
        issues.append("Missing critical invariant tests")

    if issues:
        print("\n".join(issues))
        print(f"\n❌ QUALITY CHECK FAILED: {len(issues)} issues")
        sys.exit(1)
    else:
        print("✅ ALL QUALITY CHECKS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Priority Test Cases (Immediate)

### P0: Must Have for Beta 9.1

1. **`test_overlap_is_appropriate_for_chunk_duration`** (chunked_processor)
   - Validates overlap < chunk_duration / 2
   - Prevents the Nov 6 bug from recurring

2. **`test_chunks_cover_entire_duration_no_gaps`** (chunked_processor)
   - Validates concatenated chunks = original duration
   - Detects gaps/overlaps

3. **`test_pagination_returns_all_items_exactly_once`** (library, albums, artists)
   - Validates no duplicates, no missing items
   - Prevents pagination bugs

4. **`test_processing_preserves_sample_count`** (hybrid_processor)
   - Validates len(output) == len(input)
   - Detects audio truncation

5. **`test_api_endpoints_respond_within_timeout`** (all routers)
   - Validates response times < 1s
   - Detects performance regressions

### P1: Should Have for Beta 9.1

6. **`test_chunk_boundaries_are_continuous`** (chunked_processor)
7. **`test_library_scan_is_idempotent`** (library_manager)
8. **`test_empty_library_pagination`** (library)
9. **`test_single_item_pagination`** (library)
10. **`test_exact_page_boundary_pagination`** (library)

### P2: Nice to Have for Beta 9.1

11-50. Edge cases, security tests, additional integration tests

---

## Roadmap Summary

### Beta 9.1 (December 2024)
- **Add 300 tests** (445 → 745 total)
- Focus: Invariants, integration, boundaries
- Organize with test markers
- CI quality gates

### Beta 10.0 (Q1 2025)
- **Add 600 tests** (745 → 1,345 total)
- Focus: Property-based, mutation, frontend, performance
- 85% backend coverage, 80% frontend coverage
- >80% mutation score

### Beta 11.0 (Q2 2025)
- **Add 1,155 tests** (1,345 → 2,500 total)
- Focus: E2E, visual regression, load testing
- Test-to-code ratio ≥1.0
- TDD workflow established

---

**Document Owner:** Engineering Team
**Next Review:** December 2024 (after Phase 1 completion)
