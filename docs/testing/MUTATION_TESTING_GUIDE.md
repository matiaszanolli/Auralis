# Mutation Testing Guide for Auralis

**Status**: Framework Ready, Execution Pending
**Date**: November 8, 2025
**Tool**: mutmut 3.3.1

---

## What is Mutation Testing?

**Mutation testing** validates the quality of your tests by introducing small bugs (mutations) into your code and checking if your tests catch them.

### The Problem It Solves

**Traditional Coverage** tells you which lines were executed:
```python
def divide(a, b):
    return a / b  # ✅ Line covered (test executed it)
```

Test:
```python
def test_divide():
    result = divide(10, 2)
    assert result > 0  # ❌ Weak assertion! Doesn't verify correctness
```

**Coverage**: 100% ✅
**Mutation Score**: 0% ❌ (test doesn't catch bugs)

**Mutation Testing** introduces bugs:
```python
# Mutation 1: Change / to *
def divide(a, b):
    return a * b  # Bug introduced!

# Test still passes! ❌
def test_divide():
    result = divide(10, 2)
    assert result > 0  # Still true for 10 * 2 = 20
```

**Result**: **Surviving mutant** - test didn't catch the bug!

**Better Test**:
```python
def test_divide():
    result = divide(10, 2)
    assert result == 5  # ✅ Specific assertion
    # Now catches / → * mutation
```

---

## Installation

```bash
# Install mutmut
pip install mutmut

# Verify installation
mutmut --version
```

---

## Configuration

### setup.cfg

Create `setup.cfg` in project root:

```ini
[mutmut]
# Paths to mutate (start with critical modules)
paths_to_mutate=auralis/library/cache.py

# Test directory
tests_dir=tests/

# Test runner command
runner=python -m pytest -x --tb=short

# Paths to exclude (optional)
paths_to_exclude=tests/,scripts/,docs/
```

### .mutmut-config.py (Optional)

Advanced configuration in `.mutmut-config.py`:

```python
def pre_mutation(context):
    """Called before running mutations"""
    # Setup: create temp files, configure environment
    pass

def post_mutation(context):
    """Called after each mutation"""
    # Cleanup: remove temp files, reset state
    pass
```

---

## Running Mutation Testing

### Basic Workflow

```bash
# 1. Run mutation testing
mutmut run

# 2. View results
mutmut results

# 3. Show surviving mutants
mutmut show

# 4. View specific mutant
mutmut show 1

# 5. Apply a mutant to see the actual code change
mutmut apply 1
```

### Incremental Testing

```bash
# Test only specific files
mutmut run --paths-to-mutate auralis/library/cache.py

# Run on specific mutants
mutmut run 1 5 10

# Use multiple cores
mutmut run --max-children 4
```

### Results Analysis

```bash
# Summary statistics
mutmut results

# Example output:
# Survived: 5
# Killed: 45
# Timeout: 0
# Suspicious: 0
# Skipped: 0
#
# Mutation score: 90.0%

# Show all surviving mutants
mutmut show all

# Generate HTML report (requires mutmut-browse plugin)
mutmut browse
```

---

## Mutation Score Targets

### Industry Standards

- **< 60%**: Poor - Most tests are weak
- **60-75%**: Fair - Some good tests, many weak
- **75-85%**: Good - Solid test quality
- **> 85%**: Excellent - High-quality tests
- **> 95%**: Outstanding - Exceptional test suite

### Auralis Targets

**Phase 3 Week 9 Goals**:

| Module | Lines | Mutation Score Target | Priority |
|--------|-------|----------------------|----------|
| `auralis/library/cache.py` | 255 | > 80% | P0 |
| `auralis/library/repositories/track_repository.py` | 611 | > 75% | P0 |
| `auralis/dsp/stages.py` | ~300 | > 75% | P1 |
| `auralis/core/hybrid_processor.py` | 409 | > 70% | P1 |
| `auralis/player/realtime/processor.py` | ~200 | > 80% | P1 |

**Overall Target**: **> 80% mutation score** on critical path code

---

## Types of Mutations

Mutmut introduces these types of mutations:

### 1. Arithmetic Operator Mutations

```python
# Original
result = a + b

# Mutations:
result = a - b  # Addition → Subtraction
result = a * b  # Addition → Multiplication
result = a / b  # Addition → Division
```

### 2. Comparison Operator Mutations

```python
# Original
if x > 5:

# Mutations:
if x >= 5:  # > → >=
if x < 5:   # > → <
if x == 5:  # > → ==
if x != 5:  # > → !=
```

### 3. Boolean Operator Mutations

```python
# Original
if a and b:

# Mutations:
if a or b:   # and → or
if a:        # Remove second condition
if b:        # Remove first condition
```

### 4. Constant Mutations

```python
# Original
count = 10

# Mutations:
count = 11   # Increment
count = 9    # Decrement
count = 0    # Replace with zero
```

### 5. Return Value Mutations

```python
# Original
def is_valid():
    return True

# Mutations:
def is_valid():
    return False  # True → False
    return None   # True → None
```

---

## Analyzing Surviving Mutants

### Example: Cache TTL Mutation

**Original Code** (`auralis/library/cache.py`):
```python
class QueryCache:
    def __init__(self, ttl=300):  # 5 minutes
        self.ttl = ttl

    def is_expired(self, timestamp):
        return time.time() - timestamp > self.ttl
```

**Mutation 1**: Change `>` to `>=`
```python
return time.time() - timestamp >= self.ttl  # Mutation
```

**Test**:
```python
def test_cache_expiration():
    cache = QueryCache(ttl=300)
    old_timestamp = time.time() - 400
    assert cache.is_expired(old_timestamp)  # ✅ Still passes!
```

**Problem**: Test doesn't check the exact boundary condition.

**Better Test** (kills the mutant):
```python
def test_cache_expiration_exact_boundary():
    cache = QueryCache(ttl=300)

    # Just expired
    just_expired = time.time() - 301
    assert cache.is_expired(just_expired), "Should be expired at TTL + 1"

    # Not yet expired
    not_expired = time.time() - 299
    assert not cache.is_expired(not_expired), "Should not be expired at TTL - 1"

    # Exactly at TTL (boundary case)
    exactly_ttl = time.time() - 300
    # This test now kills the >= mutation!
    assert not cache.is_expired(exactly_ttl), "Should not be expired exactly at TTL"
```

---

## Common Weak Test Patterns

### 1. Vague Assertions

❌ **Weak**:
```python
def test_process_audio():
    result = processor.process(audio)
    assert result is not None  # Too vague!
    assert len(result) > 0     # Doesn't verify correctness
```

✅ **Strong**:
```python
def test_process_audio():
    result = processor.process(audio)
    assert isinstance(result, np.ndarray)
    assert result.shape == audio.shape  # Specific shape
    assert not np.any(np.isnan(result))  # No NaN values
    assert np.abs(result).max() <= 1.0   # Amplitude range
```

### 2. Missing Boundary Tests

❌ **Weak**:
```python
def test_pagination():
    results = repo.get_all(limit=10, offset=0)
    assert len(results) <= 10  # Doesn't test exact behavior
```

✅ **Strong**:
```python
def test_pagination_exact_boundary():
    # Create exactly 25 tracks
    for i in range(25):
        repo.add({'title': f'Track {i}'})

    # First page
    page1 = repo.get_all(limit=10, offset=0)
    assert len(page1) == 10, "First page should have exactly 10"

    # Last page
    page3 = repo.get_all(limit=10, offset=20)
    assert len(page3) == 5, "Last page should have exactly 5"

    # Beyond last page
    page4 = repo.get_all(limit=10, offset=30)
    assert len(page4) == 0, "Beyond last page should be empty"
```

### 3. Missing Error Case Tests

❌ **Weak**:
```python
def test_divide():
    result = divide(10, 2)
    assert result == 5  # Only happy path
```

✅ **Strong**:
```python
def test_divide_success():
    result = divide(10, 2)
    assert result == 5

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)  # Error case tested

def test_divide_negative_numbers():
    result = divide(-10, 2)
    assert result == -5  # Edge case tested
```

---

## Mutation Testing Workflow

### Step 1: Run Baseline

```bash
# Run mutation testing
mutmut run

# View results
mutmut results
```

Example output:
```
Survived: 12
Killed: 38
Timeout: 0
Suspicious: 0

Mutation score: 76.0%
```

### Step 2: Analyze Survivors

```bash
# Show all surviving mutants
mutmut show

# Show specific mutant
mutmut show 1
```

Example output:
```
--- auralis/library/cache.py
+++ auralis/library/cache.py
@@ -45,7 +45,7 @@
     def is_expired(self, timestamp):
-        return time.time() - timestamp > self.ttl
+        return time.time() - timestamp >= self.ttl
```

### Step 3: Write Targeted Tests

Create test file `tests/mutation/test_cache_mutations.py`:

```python
"""
Mutation-Killing Tests for Cache Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests specifically designed to kill surviving mutants.
"""

import pytest
import time
from auralis.library.cache import QueryCache


@pytest.mark.mutation
class TestCacheBoundaryMutations:
    """Tests that kill boundary condition mutations."""

    def test_ttl_exact_boundary_kills_ge_mutation(self):
        """
        MUTATION: Kills > → >= mutation in is_expired().

        Mutant:
            return time.time() - timestamp >= self.ttl

        This test verifies that at exactly TTL, the cache is NOT expired.
        The >= mutation would make it expired, causing test to fail.
        """
        cache = QueryCache(ttl=300)

        # Timestamp exactly at TTL seconds ago
        exactly_ttl = time.time() - 300

        # Should NOT be expired (> is false, >= would be true)
        assert not cache.is_expired(exactly_ttl), \
            "Cache should not be expired exactly at TTL"

    def test_ttl_plus_one_is_expired_kills_lt_mutation(self):
        """
        MUTATION: Kills > → < mutation in is_expired().
        """
        cache = QueryCache(ttl=300)

        # Timestamp TTL + 1 seconds ago
        just_expired = time.time() - 301

        # Should be expired (> is true, < would be false)
        assert cache.is_expired(just_expired), \
            "Cache should be expired at TTL + 1"
```

### Step 4: Verify Improvements

```bash
# Run mutation testing again
mutmut run

# Check if mutation score improved
mutmut results
```

Expected improvement:
```
Survived: 10 (was 12) ✅
Killed: 40 (was 38) ✅
Timeout: 0
Suspicious: 0

Mutation score: 80.0% (was 76.0%) ✅
```

### Step 5: Iterate

Repeat steps 2-4 until target mutation score achieved.

---

## Critical Modules Priority List

### Phase 3 Week 9 Schedule

**Day 1-2: Cache Module**
- File: `auralis/library/cache.py` (255 lines)
- Current tests: `tests/library/test_cache.py`
- Target: > 80% mutation score
- Create: `tests/mutation/test_cache_mutations.py`

**Day 3-4: Track Repository**
- File: `auralis/library/repositories/track_repository.py` (611 lines)
- Current tests: Multiple test files
- Target: > 75% mutation score
- Create: `tests/mutation/test_track_repository_mutations.py`

**Day 5-6: DSP Stages**
- File: `auralis/dsp/stages.py` (~300 lines)
- Current tests: `tests/auralis/dsp/test_stages.py`
- Target: > 75% mutation score
- Create: `tests/mutation/test_dsp_stages_mutations.py`

**Day 7: Analysis & Documentation**
- Analyze overall results
- Document weak test patterns found
- Create improvement recommendations
- Write Phase 3 Week 9 completion document

---

## Best Practices

### 1. Start Small

❌ Don't mutate entire codebase at once
✅ Start with one critical module (< 300 lines)

### 2. Fix Test Imports First

Ensure all tests run successfully before mutation testing:
```bash
python -m pytest tests/ -v
```

### 3. Use Specific Test Runner

```ini
[mutmut]
# Use -x to stop on first failure (faster)
runner=python -m pytest -x --tb=short

# Or run only specific test file
runner=python -m pytest tests/library/test_cache.py -x
```

### 4. Document Mutants

When you kill a mutant, document why in the test:
```python
def test_kills_plus_to_minus_mutation():
    """
    MUTATION: Kills + → - mutation in calculate_total().

    Original: total = price + tax
    Mutant:   total = price - tax

    This test verifies correct addition.
    """
    result = calculate_total(price=100, tax=10)
    assert result == 110, "Should add price and tax"
```

### 5. Accept Reasonable Survivors

Not all surviving mutants are problems:

**Acceptable Survivors**:
- Logging statements
- Debug code
- Error messages (text changes)
- Comments

**Unacceptable Survivors**:
- Business logic
- Calculations
- Conditionals
- Return values

---

## Example: Complete Mutation Testing Session

### Setup

```bash
# Configure for cache module
cat > setup.cfg <<EOF
[mutmut]
paths_to_mutate=auralis/library/cache.py
tests_dir=tests/
runner=python -m pytest tests/library/test_cache.py -x --tb=short
EOF
```

### Run

```bash
# Run mutations
mutmut run

# Output:
# Generating mutants... done
# Running tests: ████████████ 50/50
#
# Survived: 8
# Killed: 42
# Mutation score: 84.0%
```

### Analyze

```bash
# Show survivors
mutmut show

# Mutant 3:
# - return time.time() - timestamp > self.ttl
# + return time.time() - timestamp >= self.ttl

# Mutant 7:
# - if key in self.cache:
# + if key not in self.cache:

# Mutant 12:
# - return self.cache.get(key, None)
# + return self.cache.get(key, False)
```

### Fix

Create `tests/mutation/test_cache_mutations.py`:

```python
def test_ttl_boundary_kills_ge_mutation():
    """Kills >= mutation in is_expired()"""
    cache = QueryCache(ttl=300)
    exactly_ttl = time.time() - 300
    assert not cache.is_expired(exactly_ttl)

def test_key_presence_kills_not_mutation():
    """Kills 'in' → 'not in' mutation"""
    cache = QueryCache()
    cache.set('key', 'value')

    # This should hit cache
    result = cache.get('key')
    assert result == 'value'

    # This should miss cache
    result = cache.get('missing')
    assert result is None

def test_default_value_kills_false_mutation():
    """Kills None → False mutation in default"""
    cache = QueryCache()
    result = cache.get('missing')

    # Must be None, not False
    assert result is None
    assert result is not False  # Kills the mutation!
```

### Verify

```bash
# Run again
mutmut run

# Output:
# Survived: 5 ✅ (was 8)
# Killed: 45 ✅ (was 42)
# Mutation score: 90.0% ✅ (was 84.0%)
```

---

## Troubleshooting

### Issue: Tests fail during mutation collection

**Error**:
```
ImportError: cannot import name 'LibraryManager'
```

**Fix**: Ensure all tests pass before mutation testing:
```bash
python -m pytest tests/ -x
```

Fix any import errors in test files first.

### Issue: Mutation testing too slow

**Problem**: Testing entire codebase takes hours.

**Solution 1**: Test one module at a time:
```ini
[mutmut]
paths_to_mutate=auralis/library/cache.py  # Just one file
```

**Solution 2**: Use parallel execution:
```bash
mutmut run --max-children 4  # Use 4 cores
```

**Solution 3**: Run only specific tests:
```ini
[mutmut]
runner=python -m pytest tests/library/test_cache.py -x
```

### Issue: Too many surviving mutants

**Problem**: 50%+ mutants survive.

**Root Cause**: Tests are too weak (vague assertions, missing edge cases).

**Solution**: Systematically add targeted tests:
1. Analyze each surviving mutant
2. Write specific test to kill it
3. Document the mutation being killed
4. Re-run to verify

---

## Metrics and Reporting

### Tracking Progress

Create `mutation_results.md`:

```markdown
# Mutation Testing Progress

## auralis/library/cache.py

| Date | Mutants | Killed | Survived | Score | Notes |
|------|---------|--------|----------|-------|-------|
| Nov 8 | 50 | 42 | 8 | 84.0% | Initial baseline |
| Nov 9 | 50 | 45 | 5 | 90.0% | Added boundary tests |
| Nov 10 | 50 | 48 | 2 | 96.0% | Added edge case tests |

## auralis/library/repositories/track_repository.py

| Date | Mutants | Killed | Survived | Score | Notes |
|------|---------|--------|----------|-------|-------|
| Nov 11 | 120 | 85 | 35 | 70.8% | Initial baseline |
| ... | ... | ... | ... | ... | ... |
```

### CI/CD Integration

Add to `.github/workflows/tests.yml`:

```yaml
- name: Mutation Testing
  run: |
    pip install mutmut
    mutmut run
    mutmut results > mutation_results.txt

    # Fail if mutation score < 80%
    SCORE=$(grep "Mutation score" mutation_results.txt | awk '{print $3}' | sed 's/%//')
    if (( $(echo "$SCORE < 80" | bc -l) )); then
      echo "Mutation score $SCORE% is below 80% threshold"
      exit 1
    fi
```

---

## Summary

**Mutation testing validates test quality by:**
1. Introducing bugs (mutations) into code
2. Running test suite against mutated code
3. Measuring how many mutations are caught (killed)
4. Identifying weak tests (surviving mutants)

**Target**: **> 80% mutation score** on critical modules

**Next Steps**:
1. Fix test import errors
2. Run mutation testing on `auralis/library/cache.py`
3. Analyze surviving mutants
4. Write targeted tests to kill survivors
5. Repeat for other critical modules

**Expected Outcome**: High-quality test suite that catches real bugs, not just executes lines.
