# Integration Guide: Auto-Issue Creation

This guide shows how to add auto-issue creation to your **existing** GitHub Actions workflows.

## Quick Integration (Minimal Changes)

### Option 1: Add to Existing CI Workflow

Add these steps to [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

```yaml
# Add to permissions at the top
permissions:
  contents: read
  pull-requests: write
  checks: write
  issues: write  # ADD THIS LINE

jobs:
  test-python:
    steps:
    # ... existing steps ...

    # MODIFY: Add --junitxml flag to your pytest command
    - name: Run tests with coverage
      id: python_tests  # ADD THIS ID
      continue-on-error: true  # CHANGE: from || true to this
      run: |
        python -m pytest tests/ -v \
          --cov=auralis --cov=auralis-web/backend \
          --cov-report=xml --cov-report=term-missing \
          --timeout=300 \
          --junitxml=test-results.xml \  # ADD THIS LINE
          --ignore=tests/backend/test_state_manager.py \
          -m "not slow"

    # ADD: Install PyGithub
    - name: Install issue creation dependencies
      if: always()
      run: pip install PyGithub

    # ADD: Create issues from failures
    - name: Create issues from test failures
      if: always() && steps.python_tests.outcome == 'failure'
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        python .github/scripts/create_test_issues.py \
          --junit-xml test-results.xml \
          --repo ${{ github.repository }}

    # ADD: Fail workflow after creating issues
    - name: Report test status
      if: steps.python_tests.outcome == 'failure'
      run: |
        echo "::error::Tests failed. Issues created for failures."
        exit 1
```

### Option 2: Use New Dedicated Workflow

Simply enable the new workflow we created:

```bash
# The workflow is already created at:
.github/workflows/test-with-issue-creation.yml

# Just push it and it will run automatically
git add .github/workflows/test-with-issue-creation.yml
git commit -m "ci: Add auto-issue creation for test failures"
git push
```

## Progressive Rollout Strategy

### Phase 1: Test in Isolation (Recommended Start Here)

1. **Create a test branch:**
   ```bash
   git checkout -b test/auto-issue-creation
   ```

2. **Test with dry-run locally:**
   ```bash
   # Run tests to generate failures
   pytest tests/ --junitxml=test-results.xml -m "not slow"

   # Test issue creation in dry-run mode
   python .github/scripts/create_test_issues.py \
     --junit-xml test-results.xml \
     --repo matiaszanolli/Auralis \
     --dry-run
   ```

3. **Verify output** - it should show what issues would be created

### Phase 2: Enable for One Test Suite

Start with just backend tests:

```yaml
# In .github/workflows/backend-tests.yml
- name: Run backend tests
  id: backend_tests
  continue-on-error: true
  run: |
    python -m pytest tests/backend/ -v \
      --junitxml=test-results-backend.xml  # Add this

- name: Create issues
  if: always() && steps.backend_tests.outcome == 'failure'
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    pip install PyGithub
    python .github/scripts/create_test_issues.py \
      --junit-xml test-results-backend.xml \
      --repo ${{ github.repository }}
```

### Phase 3: Roll Out to All Tests

Once validated, apply to all test workflows.

## Configuration Options

### Change Labels

Edit `.github/scripts/create_test_issues.py` line 75-88:

```python
@property
def labels(self) -> List[str]:
    """Labels to apply to the issue."""
    labels = ['bug', 'auto-test-failure', 'ci']

    # Customize as needed
    if 'critical' in self.test_name.lower():
        labels.append('priority-high')

    return labels
```

### Filter Which Tests Create Issues

Only create issues for certain test patterns:

```python
# In create_test_issues.py, add to parse_junit_xml():
if 'integration' in test_file or 'critical' in test_name:
    failures.append(TestFailure(...))
```

### Customize Issue Template

Edit the `issue_body` property in `.github/scripts/create_test_issues.py` (line 46).

## Preventing Issue Spam

### Limit Issues Per Run

Add to the script before creating issues:

```python
MAX_ISSUES = 10
if len(failures) > MAX_ISSUES:
    print(f"WARNING: {len(failures)} failures. Creating issues for first {MAX_ISSUES} only.")
    failures = failures[:MAX_ISSUES]
```

### Only Create on Main Branch

In your workflow:

```yaml
- name: Create issues from test failures
  if: |
    always() &&
    steps.tests.outcome == 'failure' &&
    github.ref == 'refs/heads/master'  # Only on main branch
```

### Skip for PRs

```yaml
- name: Create issues from test failures
  if: |
    always() &&
    steps.tests.outcome == 'failure' &&
    github.event_name != 'pull_request'  # Skip on PRs
```

## Testing the Integration

### 1. Dry Run Test

```bash
# Generate test results
pytest tests/ --junitxml=test-results.xml --tb=short || true

# Test issue creation
python .github/scripts/create_test_issues.py \
  --junit-xml test-results.xml \
  --repo matiaszanolli/Auralis \
  --dry-run
```

### 2. Create Test Issues Manually

```bash
# Set your GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# Create actual issues (use a test repo first!)
python .github/scripts/create_test_issues.py \
  --junit-xml test-results.xml \
  --repo matiaszanolli/Auralis
```

### 3. Verify Duplicate Prevention

Run the script twice with the same test results:

```bash
python .github/scripts/create_test_issues.py --junit-xml test-results.xml --repo matiaszanolli/Auralis
# Should create issues

python .github/scripts/create_test_issues.py --junit-xml test-results.xml --repo matiaszanolli/Auralis
# Should update existing issues, not create duplicates
```

## Monitoring

### View Auto-Generated Issues

```bash
# Using GitHub CLI
gh issue list --label auto-test-failure

# Get count
gh issue list --label auto-test-failure --json number --jq 'length'
```

### Clean Up All Auto-Issues

```bash
# Close all auto-generated test failure issues
gh issue list --label auto-test-failure --state open --json number \
  --jq '.[].number' | xargs -I {} gh issue close {}
```

## Troubleshooting

### Issue: No JUnit XML generated

**Solution:** Ensure pytest has the plugin:
```bash
pip install pytest  # Already includes junit-xml support
```

### Issue: Permission denied creating issues

**Solution:** Check workflow permissions:
```yaml
permissions:
  issues: write  # Required
```

### Issue: Issues not auto-closing

**Cause:** Script needs to run even when tests pass

**Solution:** Ensure workflow runs on success:
```yaml
- name: Create issues from test failures
  if: always()  # Run even if tests pass
```

## Best Practices

1. **Start Small**: Begin with one test suite
2. **Monitor First Week**: Watch for spam or duplicates
3. **Adjust Labels**: Customize based on your triage process
4. **Regular Cleanup**: Close stale issues periodically
5. **Document**: Add to your CONTRIBUTING.md that issues may be auto-created

## Next Steps

Once integrated, consider:

- Setting up issue templates for auto-generated issues
- Creating a dashboard for test health metrics
- Adding Slack/email notifications for critical test failures
- Implementing retry logic for flaky tests before creating issues
