# GitHub Actions Scripts

## Auto-Issue Creation from Test Failures

The `create_test_issues.py` script automatically creates GitHub issues from test failures without creating duplicates.

### How It Works

1. **Unique Identification**: Each test failure gets a unique ID based on `file_path::test_name`
2. **Duplicate Prevention**: Before creating an issue, the script checks if one already exists
3. **Auto-Update**: If a test keeps failing, the existing issue is updated with a comment
4. **Auto-Close**: When a test starts passing, its issue is automatically closed

### Issue Format

Issues created by this script include:

- **Title**: `Test Failure: {test_name}`
- **Labels**: `bug`, `auto-test-failure`, `ci`, plus context-specific labels (`backend`, `frontend`, etc.)
- **Body**: Contains:
  - Test name, file, and suite
  - Full error message
  - Link to failing workflow run
  - Unique identifier (hidden HTML comment for deduplication)

### Usage

#### In GitHub Actions

```yaml
- name: Run tests with JUnit output
  id: tests
  continue-on-error: true
  run: pytest tests/ --junitxml=test-results.xml

- name: Create issues from test failures
  if: always() && steps.tests.outcome == 'failure'
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    python .github/scripts/create_test_issues.py \
      --junit-xml test-results.xml \
      --repo ${{ github.repository }}
```

#### Manual Testing (Dry Run)

```bash
# Test locally without creating issues
python .github/scripts/create_test_issues.py \
  --junit-xml test-results.xml \
  --repo owner/repo \
  --dry-run
```

#### Manual Execution

```bash
# Create issues from local test run
export GITHUB_TOKEN="your_token_here"
python .github/scripts/create_test_issues.py \
  --junit-xml test-results.xml \
  --repo matiaszanolli/Auralis
```

### Requirements

```bash
pip install PyGithub
```

### Configuration

The script uses environment variables from GitHub Actions:

- `GITHUB_TOKEN`: For authentication (automatically provided in workflows)
- `GITHUB_REPOSITORY`: Repository name (automatically provided)
- `GITHUB_RUN_ID`: Workflow run ID for linking
- `GITHUB_SHA`: Commit SHA for reference
- `GITHUB_SERVER_URL`: GitHub server URL

### Labels Applied

- `auto-test-failure`: All auto-generated issues
- `ci`: Indicates CI-detected issue
- `bug`: Standard bug label
- `backend` / `frontend`: Context-specific
- `assertion-error` / `timeout`: Error-type specific

### Customization

To modify label logic, edit the `TestFailure.labels` property in `create_test_issues.py`.

To change issue title/body format, edit the `issue_title` and `issue_body` properties.

### Cleaning Up Old Issues

Auto-generated issues are automatically closed when tests pass. To manually clean up:

```bash
# Close all auto-test-failure issues
gh issue list --label auto-test-failure --state open --json number --jq '.[].number' | \
  xargs -I {} gh issue close {}
```

### Troubleshooting

**Issue: "PyGithub not installed"**
- Solution: Add `pip install PyGithub` to your workflow

**Issue: "Permission denied"**
- Solution: Ensure your workflow has `issues: write` permission

**Issue: Duplicate issues still created**
- Check that the unique_id HTML comment is in the issue body
- Verify the test path/name hasn't changed

**Issue: Issues not auto-closing**
- Ensure the workflow runs on successful test runs too
- Check that the unique_id matches between failure and success
