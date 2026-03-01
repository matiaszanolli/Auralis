# Test Generation

Generate regression and unit tests following established project patterns.

**Input**: `$ARGUMENTS` = file path, issue number, commit hash, or empty (uncommitted changes)

## Step 1: Determine Target

Parse `$ARGUMENTS`:

- **File path** (e.g. `auralis/core/simple_mastering.py`): Generate tests for that file
- **Issue number** (e.g. `2613`): Generate regression test for the fix via `gh issue view`
- **Commit hash** (e.g. `abc1234`): Generate tests for changes in that commit via `git show --stat`
- **Empty**: Generate tests for uncommitted changes via `git diff --name-only`

## Step 2: Study Existing Tests

Before writing ANY test, study 2-3 existing tests in the target directory to match style:

```bash
# Find existing tests for the target module
find tests/ -name "*.py" -path "*<module_name>*" | head -5
```

Read the found test files and note:
- Import patterns and fixtures used
- Assertion style (pytest asserts, parametrize, etc.)
- Mock patterns (unittest.mock, monkeypatch, etc.)
- Marker usage (`@pytest.mark.regression`, domain markers from `pytest.ini`)
- Setup/teardown patterns

## Step 3: Generate Tests

### Python Tests (pytest)

Follow `docs/development/TESTING_GUIDELINES.md`:

- **Test invariants, not implementation**: Assert WHAT should be true, not HOW it's computed
- **Markers**: Use `@pytest.mark.regression` for regression tests + domain markers from `pytest.ini`
- **Naming**: `test_<function_name>_<scenario>` or `test_<issue_number>_<description>`
- **Structure**: Arrange/Act/Assert pattern
- **Isolation**: Each test must be independent — no shared mutable state between tests

#### DSP Tests MUST assert all 4:

```python
# 1. Sample count preserved
assert len(output) == len(input), "Sample count changed"

# 2. Dtype preserved
assert output.dtype == input.dtype, f"Dtype changed: {input.dtype} -> {output.dtype}"

# 3. Finite values (no NaN/Inf)
assert np.all(np.isfinite(output)), "Output contains NaN or Inf"

# 4. Clipping range
assert np.all(output >= -1.0) and np.all(output <= 1.0), "Output exceeds [-1.0, 1.0]"
```

#### DB/Repository Tests MUST cover:

- Repository method returns correct data
- Missing record handling (returns None, not crash)
- Concurrent access safety (if applicable)

#### Regression Tests:

- MUST fail if the fix is reverted — test the exact condition that caused the bug
- Reference the issue number in test name and docstring
- Include the minimal reproduction case from the issue

### Frontend Tests (Vitest)

- Use `render`/`screen` from `@/test/test-utils`
- Use `vi.fn()` for mocks, `vi.spyOn()` for spying
- Use `userEvent` for user interactions, not `fireEvent`
- Test component behavior, not implementation details
- Include loading, error, and empty states

```typescript
import { render, screen } from '@/test/test-utils';
import { vi, describe, it, expect } from 'vitest';
```

## Step 4: Place Test Files

- Python: Place in the corresponding `tests/` subdirectory matching the source structure
- Frontend: Co-locate with component or place in `src/test/` if cross-cutting

## Step 5: Verify

Run the generated tests to confirm they pass:

```bash
# Python
python -m pytest <test-file> -vv -s 2>&1 | tail -40

# Frontend
cd auralis-web/frontend && npx vitest run <test-file> 2>&1 | tail -40
```

If generating a regression test, also verify it WOULD fail without the fix:
- Read the fix commit/diff
- Mentally trace: if the fix were reverted, would this test catch it?
- If not, revise the test to be more specific

## Output

- Generated test file(s) with file paths
- Pass/fail verification results
- For regression tests: confirmation that the test targets the exact fix condition
