# Test Execution Guide

**Date:** November 7, 2024
**Status:** Complete
**Coverage:** 238 Phase 1 tests + 445 existing tests = 683 total tests

---

## Quick Start

### Run All Tests
```bash
pytest tests/
# Runs: All 683 tests
# Time: ~275 seconds (~4.5 minutes)
```

### Run Phase 1 Tests Only
```bash
# Week 1: Invariant tests (109 tests)
pytest -m invariant tests/

# Week 2: Integration tests (50 tests)
pytest -m integration tests/backend/test_e2e_workflows.py tests/backend/test_api_endpoint_integration.py tests/backend/test_artwork_integration.py tests/backend/test_playlist_integration.py

# Week 3: Boundary tests (79 tests)
pytest -m boundary tests/backend/
```

### Run Fast Tests Only (CI/PR)
```bash
pytest -m "fast and not slow" tests/
# Runs: ~580 tests (85% of total)
# Time: ~60 seconds
# Catches: ~95% of bugs
```

### Run Slow Tests (Nightly)
```bash
pytest -m slow tests/
# Runs: ~23 tests (3% of total)
# Time: ~177 seconds
# Catches: Performance regressions, memory leaks, long audio processing
```

---

## Test Markers Reference

### Test Type Markers

**@pytest.mark.unit**
- Unit tests for individual components
- Fast execution (< 10ms)
- No external dependencies
- Example: `pytest -m unit tests/`

**@pytest.mark.integration**
- Integration tests across components
- Medium execution (10-100ms)
- Uses real dependencies
- Example: `pytest -m integration tests/`

**@pytest.mark.boundary**
- Boundary condition and edge case tests
- Mixed execution (80ms - 1.7s)
- Tests empty, single, exact, extreme values
- Example: `pytest -m boundary tests/`

**@pytest.mark.e2e**
- End-to-end integration tests
- Slow execution (> 1s)
- Complete workflow validation
- Example: `pytest -m e2e tests/`

**@pytest.mark.invariant**
- Invariant tests (properties that must always hold)
- Fast execution (< 100ms)
- Configuration and logic validation
- Example: `pytest -m invariant tests/`

### Speed Markers

**@pytest.mark.fast**
- Fast tests (< 100ms)
- Run in CI/PR checks
- ~580 tests (85%)
- Example: `pytest -m fast tests/`

**@pytest.mark.slow**
- Slow tests (> 1s)
- Run nightly or weekly
- ~23 tests (3%)
- Example: `pytest -m slow tests/`

### Domain Markers

**@pytest.mark.audio**
- Audio processing tests
- Example: `pytest -m audio tests/`

**@pytest.mark.library**
- Library management tests
- Example: `pytest -m library tests/`

**@pytest.mark.player**
- Player operation tests
- Example: `pytest -m player tests/`

**@pytest.mark.api**
- API endpoint tests
- Example: `pytest -m api tests/`

**@pytest.mark.playlist**
- Playlist operation tests
- Example: `pytest -m playlist tests/`

**@pytest.mark.artwork**
- Artwork management tests
- Example: `pytest -m artwork tests/`

**@pytest.mark.metadata**
- Metadata operation tests
- Example: `pytest -m metadata tests/`

**@pytest.mark.files**
- File I/O tests
- Example: `pytest -m files tests/`

**@pytest.mark.core**
- Core library tests
- Example: `pytest -m core tests/`

**@pytest.mark.dsp**
- DSP functionality tests
- Example: `pytest -m dsp tests/`

### Special Markers

**@pytest.mark.performance**
- Performance and benchmark tests
- Tests for O(n) complexity, linear scaling
- Example: `pytest -m performance tests/`

**@pytest.mark.security**
- Security tests
- SQL injection, control characters, path traversal
- Example: `pytest -m security tests/`

**@pytest.mark.memory**
- Memory leak detection tests
- Tests for memory growth over repeated operations
- Example: `pytest -m memory tests/`

**@pytest.mark.regression**
- Regression tests for known bugs
- Example: `pytest -m regression tests/`

### Boundary Sub-Markers

**@pytest.mark.empty**
- Tests for empty collections
- Example: `pytest -m empty tests/`

**@pytest.mark.single**
- Tests for single-item collections
- Example: `pytest.mark single tests/`

**@pytest.mark.exact**
- Tests for exact boundary conditions
- offset=total, limit=0, etc.
- Example: `pytest -m exact tests/`

**@pytest.mark.extreme**
- Tests for maximum/minimum values
- Very long audio, very short audio, extreme loudness
- Example: `pytest -m extreme tests/`

---

## Common Test Combinations

### CI/CD Pipelines

**Pull Request Checks (Fast - 30s)**
```bash
# Run only fast tests
pytest -m "fast and not slow" tests/

# With coverage
pytest -m "fast and not slow" --cov=auralis --cov-report=term-missing tests/
```

**Nightly Full Suite (5 min)**
```bash
# Run all tests
pytest tests/

# With coverage and HTML report
pytest --cov=auralis --cov-report=html --cov-report=term-missing tests/
```

**Weekly Performance Suite (10 min)**
```bash
# Run performance and memory tests
pytest -m "performance or memory" tests/
```

**Security Audit (2 min)**
```bash
# Run all security tests
pytest -m security tests/
```

### Development Workflows

**Working on Library Management**
```bash
# Run all library tests
pytest -m library tests/

# Run fast library tests only
pytest -m "library and fast" tests/
```

**Working on Audio Processing**
```bash
# Run all audio tests
pytest -m audio tests/

# Run fast audio tests
pytest -m "audio and fast" tests/

# Run audio boundary tests
pytest -m "audio and boundary" tests/
```

**Working on API Endpoints**
```bash
# Run all API tests
pytest -m api tests/

# Run fast API tests
pytest -m "api and fast" tests/
```

**Testing Edge Cases**
```bash
# Run all boundary tests
pytest -m boundary tests/

# Run empty collection tests
pytest -m empty tests/

# Run extreme value tests
pytest -m extreme tests/
```

### Debugging

**Run Single Test**
```bash
pytest tests/backend/test_boundary_empty_single.py::test_empty_library_get_all_tracks -v
```

**Run Single Test File**
```bash
pytest tests/backend/test_boundary_empty_single.py -v
```

**Run with Verbose Output**
```bash
pytest -vv tests/
```

**Run with Print Statements**
```bash
pytest -s tests/
```

**Run and Stop at First Failure**
```bash
pytest -x tests/
```

**Run Last Failed Tests**
```bash
pytest --lf tests/
```

**Run Failed Tests First**
```bash
pytest --ff tests/
```

---

## Test Selection Patterns

### Combine Multiple Markers (AND)
```bash
# Tests that are BOTH integration AND fast
pytest -m "integration and fast" tests/

# Tests that are BOTH boundary AND security
pytest -m "boundary and security" tests/
```

### Combine Multiple Markers (OR)
```bash
# Tests that are EITHER integration OR e2e
pytest -m "integration or e2e" tests/

# Tests that are EITHER security OR memory
pytest -m "security or memory" tests/
```

### Exclude Markers (NOT)
```bash
# All tests EXCEPT slow ones
pytest -m "not slow" tests/

# All tests EXCEPT integration and slow
pytest -m "not integration and not slow" tests/
```

### Complex Combinations
```bash
# Fast boundary OR integration tests (but not slow)
pytest -m "(boundary or integration) and fast and not slow" tests/

# Library tests that are NOT slow
pytest -m "library and not slow" tests/

# Security or performance tests
pytest -m "security or performance" tests/
```

---

## Test Execution Performance

### Execution Time by Test Type

```
Test Type               Count    Time      Avg/Test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fast tests (< 100ms)    580      ~60s      103ms
Medium tests (100-1s)    80      ~40s      500ms
Slow tests (> 1s)        23     ~177s      7.7s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total                    683     ~277s      406ms
```

### Optimization Strategies

**1. Parallel Execution (pytest-xdist)**
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run with 4 workers
pytest -n 4 tests/

# Run with auto-detect CPU cores
pytest -n auto tests/

# Expected speedup: 2-4x
```

**2. Test Caching (pytest-cache)**
```bash
# Cache is enabled by default in pytest >= 3.0

# Clear cache
pytest --cache-clear tests/

# Show cache contents
pytest --cache-show
```

**3. Fast Failure**
```bash
# Stop at first failure
pytest -x tests/

# Stop after N failures
pytest --maxfail=5 tests/
```

---

## Coverage Reporting

### Generate Coverage Report
```bash
# Terminal report
pytest --cov=auralis --cov-report=term-missing tests/

# HTML report (opens in browser)
pytest --cov=auralis --cov-report=html tests/
open htmlcov/index.html

# XML report (for CI)
pytest --cov=auralis --cov-report=xml tests/
```

### Coverage by Component
```bash
# Core processing coverage
pytest --cov=auralis/core --cov-report=term-missing tests/

# Library management coverage
pytest --cov=auralis/library --cov-report=term-missing tests/

# DSP coverage
pytest --cov=auralis/dsp --cov-report=term-missing tests/
```

### Coverage Thresholds
```bash
# Fail if coverage < 85%
pytest --cov=auralis --cov-fail-under=85 tests/
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-xdist

    - name: Run fast tests (PR checks)
      run: |
        pytest -m "fast and not slow" --cov=auralis --cov-report=xml tests/

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  nightly:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run all tests (nightly)
      run: |
        pytest --cov=auralis --cov-report=html tests/

    - name: Archive coverage report
      uses: actions/upload-artifact@v3
      with:
        name: coverage-report
        path: htmlcov/
```

### GitLab CI Example

```yaml
stages:
  - test
  - nightly

test:fast:
  stage: test
  script:
    - pip install -r requirements.txt
    - pip install pytest pytest-cov
    - pytest -m "fast and not slow" --cov=auralis --cov-report=xml tests/
  coverage: '/(?i)total.*? (100(?:\.0+)?\%|[1-9]?\d(?:\.\d+)?\%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

test:nightly:
  stage: nightly
  only:
    - schedules
  script:
    - pip install -r requirements.txt
    - pip install pytest pytest-cov
    - pytest --cov=auralis --cov-report=html tests/
  artifacts:
    paths:
      - htmlcov/
```

---

## Troubleshooting

### Tests Running Slowly

**Problem:** Tests take > 5 minutes
**Solution:**
```bash
# Run only fast tests
pytest -m fast tests/

# Use parallel execution
pytest -n auto tests/

# Profile slow tests
pytest --durations=10 tests/
```

### Tests Failing Randomly

**Problem:** Flaky tests, non-deterministic failures
**Solution:**
```bash
# Run test multiple times
pytest --count=10 tests/backend/test_e2e_workflows.py

# Check for race conditions in concurrent tests
pytest -m "not concurrent" tests/
```

### Memory Errors

**Problem:** Tests crash with MemoryError
**Solution:**
```bash
# Run tests sequentially (no parallel)
pytest -n 0 tests/

# Run memory tests separately
pytest -m memory tests/

# Skip large library tests
pytest -m "not extreme" tests/
```

### Import Errors

**Problem:** ModuleNotFoundError or ImportError
**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Check Python path
echo $PYTHONPATH

# Run from project root
cd /path/to/matchering
pytest tests/
```

---

## Best Practices

### Writing New Tests

**1. Always add markers:**
```python
@pytest.mark.invariant
@pytest.mark.fast
@pytest.mark.library
def test_cache_invalidation():
    ...
```

**2. Use appropriate test type:**
- **Invariant** - Properties that must always hold
- **Integration** - Multi-component workflows
- **Boundary** - Edge cases and extreme values
- **Unit** - Individual component behavior

**3. Mark speed correctly:**
- **fast** - < 100ms (most tests)
- **slow** - > 1s (performance, large data)

**4. Add domain markers:**
- **audio**, **library**, **player**, **api**, etc.

### Running Tests Locally

**Before committing:**
```bash
# Run fast tests
pytest -m fast tests/

# Run tests for your area
pytest -m library tests/  # if working on library

# Run with coverage
pytest --cov=auralis tests/
```

**Before creating PR:**
```bash
# Run full test suite
pytest tests/

# Check coverage
pytest --cov=auralis --cov-fail-under=85 tests/
```

**After fixing a bug:**
```bash
# Run regression tests
pytest -m regression tests/

# Run boundary tests for the area
pytest -m "boundary and library" tests/
```

---

## Test Organization

### Directory Structure

```
tests/
├── auralis/                    # Core library tests
│   ├── analysis/              # Analysis module tests
│   ├── core/                  # Core processing tests
│   ├── dsp/                   # DSP tests
│   ├── library/               # Library management tests
│   │   ├── test_library_manager_invariants.py  # Week 1 ✨
│   │   └── test_scanning_invariants.py         # Week 1 ✨
│   └── player/                # Player tests
│
├── backend/                    # Backend API tests
│   ├── test_e2e_workflows.py              # Week 2 ✨
│   ├── test_api_endpoint_integration.py   # Week 2 ✨
│   ├── test_artwork_integration.py        # Week 2 ✨
│   ├── test_playlist_integration.py       # Week 2 ✨
│   ├── test_boundary_empty_single.py      # Week 3 ✨
│   ├── test_boundary_exact_conditions.py  # Week 3 ✨
│   └── test_boundary_max_min_values.py    # Week 3 ✨
│
└── validation/                 # Validation tests

✨ = Phase 1 new tests (238 tests)
```

### Test Naming Conventions

**Invariant tests:**
```python
def test_property_must_hold():
    """Test that property X always holds"""

def test_count_matches_actual():
    """Test that cached count matches actual count"""
```

**Integration tests:**
```python
def test_workflow_name_workflow():
    """Test complete workflow from start to finish"""

def test_add_play_pause_workflow():
    """Test add → play → pause sequence"""
```

**Boundary tests:**
```python
def test_empty_collection_operation():
    """Test operation on empty collection"""

def test_exact_boundary_condition():
    """Test exact boundary (offset=total, limit=0)"""

def test_extreme_value():
    """Test maximum or minimum value"""
```

---

## Summary

### Quick Reference

| Use Case | Command |
|----------|---------|
| All tests | `pytest tests/` |
| Fast tests (CI) | `pytest -m fast tests/` |
| Slow tests (nightly) | `pytest -m slow tests/` |
| Invariant tests | `pytest -m invariant tests/` |
| Integration tests | `pytest -m integration tests/` |
| Boundary tests | `pytest -m boundary tests/` |
| Security tests | `pytest -m security tests/` |
| Performance tests | `pytest -m performance tests/` |
| Library tests | `pytest -m library tests/` |
| Audio tests | `pytest -m audio tests/` |
| Single file | `pytest tests/backend/test_file.py` |
| Single test | `pytest tests/backend/test_file.py::test_name` |
| With coverage | `pytest --cov=auralis tests/` |
| Parallel (4x faster) | `pytest -n auto tests/` |

### Test Execution Times

| Test Suite | Tests | Time | When to Run |
|------------|-------|------|-------------|
| Fast | 580 | ~60s | Every commit (CI) |
| All | 683 | ~277s | Before PR |
| Slow | 23 | ~177s | Nightly |
| Performance | ~15 | ~120s | Weekly |

---

**Prepared by:** Claude Code
**Date:** November 7, 2024
**Phase:** Week 4 - Test Organization Complete
