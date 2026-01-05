#!/usr/bin/env python3
"""
Auto-create GitHub issues from test failures without duplicates.

Usage:
  python create_test_issues.py --junit-xml test-results.xml --repo owner/repo
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

try:
    from github import Github, GithubException
except ImportError:
    print("ERROR: PyGithub not installed. Run: pip install PyGithub", file=sys.stderr)
    sys.exit(1)


class TestFailure:
    """Represents a single test failure."""

    def __init__(self, test_name: str, test_file: str, error_message: str,
                 error_type: str, test_suite: str):
        self.test_name = test_name
        self.test_file = test_file
        self.error_message = error_message
        self.error_type = error_type
        self.test_suite = test_suite

    @property
    def unique_id(self) -> str:
        """Generate a stable, unique identifier for this test failure."""
        # Use test file path + test name for uniqueness
        identifier = f"{self.test_file}::{self.test_name}"
        return hashlib.md5(identifier.encode()).hexdigest()[:12]

    @property
    def issue_title(self) -> str:
        """Generate issue title."""
        # Keep it concise but informative
        return f"Test Failure: {self.test_name}"

    @property
    def issue_body(self) -> str:
        """Generate issue body with details."""
        workflow_run = os.getenv('GITHUB_RUN_ID', 'unknown')
        workflow_url = os.getenv('GITHUB_SERVER_URL', 'https://github.com')
        repo = os.getenv('GITHUB_REPOSITORY', 'unknown/unknown')
        sha = os.getenv('GITHUB_SHA', 'unknown')[:7]

        return f"""## Test Failure Details

**Test:** `{self.test_name}`
**File:** `{self.test_file}`
**Suite:** `{self.test_suite}`
**Error Type:** `{self.error_type}`

### Error Message
```
{self.error_message.strip()}
```

### CI Information
- **Commit:** {sha}
- **Workflow Run:** [{workflow_run}]({workflow_url}/{repo}/actions/runs/{workflow_run})

---
<!-- test-failure-id: {self.unique_id} -->
<!-- auto-generated: true -->
"""

    @property
    def labels(self) -> List[str]:
        """Labels to apply to the issue."""
        labels = ['bug', 'auto-test-failure', 'ci']

        # Add suite-specific labels
        if 'backend' in self.test_suite.lower() or 'backend' in self.test_file:
            labels.append('backend')
        elif 'frontend' in self.test_suite.lower() or 'frontend' in self.test_file:
            labels.append('frontend')

        # Add error type labels
        if 'assertion' in self.error_type.lower():
            labels.append('assertion-error')
        elif 'timeout' in self.error_type.lower():
            labels.append('timeout')

        return labels


def parse_junit_xml(xml_path: Path) -> List[TestFailure]:
    """Parse JUnit XML and extract test failures."""
    failures = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Handle both <testsuites> and <testsuite> root elements
        testsuites = root.findall('.//testsuite')
        if not testsuites:
            testsuites = [root] if root.tag == 'testsuite' else []

        for testsuite in testsuites:
            suite_name = testsuite.get('name', 'unknown')

            for testcase in testsuite.findall('testcase'):
                test_name = testcase.get('name', 'unknown')
                test_file = testcase.get('file', testcase.get('classname', 'unknown'))

                # Check for failures or errors
                failure_elem = testcase.find('failure')
                error_elem = testcase.find('error')

                if failure_elem is not None or error_elem is not None:
                    elem = failure_elem if failure_elem is not None else error_elem
                    error_message = elem.text or 'No error message'
                    error_type = elem.get('type', 'Unknown')

                    failures.append(TestFailure(
                        test_name=test_name,
                        test_file=test_file,
                        error_message=error_message,
                        error_type=error_type,
                        test_suite=suite_name
                    ))

    except ET.ParseError as e:
        print(f"ERROR: Failed to parse {xml_path}: {e}", file=sys.stderr)
        return []

    return failures


def find_existing_issue(gh_repo, unique_id: str) -> Optional[int]:
    """
    Find existing issue with this unique_id.
    Returns issue number if found, None otherwise.
    """
    # Search in open issues with our label
    query = f"repo:{gh_repo.full_name} is:issue is:open label:auto-test-failure in:body {unique_id}"

    try:
        issues = gh_repo.get_issues(state='open', labels=['auto-test-failure'])
        for issue in issues:
            if f"<!-- test-failure-id: {unique_id} -->" in issue.body:
                return issue.number
    except GithubException as e:
        print(f"WARNING: Error searching issues: {e}", file=sys.stderr)

    return None


def close_fixed_issues(gh_repo, current_failure_ids: set):
    """Close issues for tests that are now passing."""
    try:
        open_issues = gh_repo.get_issues(state='open', labels=['auto-test-failure'])

        for issue in open_issues:
            # Extract unique_id from issue body
            if '<!-- test-failure-id:' in issue.body:
                start = issue.body.find('<!-- test-failure-id:') + len('<!-- test-failure-id:')
                end = issue.body.find('-->', start)
                issue_id = issue.body[start:end].strip()

                # If this test is no longer failing, close the issue
                if issue_id not in current_failure_ids:
                    issue.create_comment(
                        "✅ This test is now passing. Auto-closing.\n\n"
                        f"Verified in workflow run: {os.getenv('GITHUB_RUN_ID', 'unknown')}"
                    )
                    issue.edit(state='closed')
                    print(f"  ✓ Closed issue #{issue.number} (test now passing)")

    except GithubException as e:
        print(f"WARNING: Error closing fixed issues: {e}", file=sys.stderr)


def create_or_update_issues(failures: List[TestFailure], repo_name: str,
                           github_token: str, dry_run: bool = False):
    """Create or update GitHub issues for test failures."""
    if not failures:
        print("✓ No test failures found!")
        return

    print(f"Found {len(failures)} test failure(s)")

    if dry_run:
        print("\n[DRY RUN MODE - No issues will be created]\n")
        for failure in failures:
            print(f"\nWould create/update issue:")
            print(f"  Title: {failure.issue_title}")
            print(f"  ID: {failure.unique_id}")
            print(f"  Labels: {', '.join(failure.labels)}")
        return

    gh = Github(github_token)
    gh_repo = gh.get_repo(repo_name)

    created = 0
    updated = 0
    current_failure_ids = {f.unique_id for f in failures}

    for failure in failures:
        existing_issue_num = find_existing_issue(gh_repo, failure.unique_id)

        if existing_issue_num:
            # Update existing issue
            try:
                issue = gh_repo.get_issue(existing_issue_num)
                issue.create_comment(
                    f"⚠️ This test is still failing.\n\n"
                    f"Workflow run: {os.getenv('GITHUB_RUN_ID', 'unknown')}\n"
                    f"Commit: {os.getenv('GITHUB_SHA', 'unknown')[:7]}"
                )
                print(f"  ↻ Updated issue #{existing_issue_num}: {failure.test_name}")
                updated += 1
            except GithubException as e:
                print(f"  ✗ Failed to update issue #{existing_issue_num}: {e}", file=sys.stderr)
        else:
            # Create new issue
            try:
                issue = gh_repo.create_issue(
                    title=failure.issue_title,
                    body=failure.issue_body,
                    labels=failure.labels
                )
                print(f"  ✓ Created issue #{issue.number}: {failure.test_name}")
                created += 1
            except GithubException as e:
                print(f"  ✗ Failed to create issue: {e}", file=sys.stderr)

    # Close issues for tests that are now passing
    print("\nChecking for fixed tests...")
    close_fixed_issues(gh_repo, current_failure_ids)

    print(f"\n✓ Summary: {created} created, {updated} updated")


def main():
    parser = argparse.ArgumentParser(
        description='Create GitHub issues from test failures'
    )
    parser.add_argument(
        '--junit-xml',
        required=True,
        help='Path to JUnit XML test results file'
    )
    parser.add_argument(
        '--repo',
        help='GitHub repository (owner/repo). Defaults to GITHUB_REPOSITORY env var'
    )
    parser.add_argument(
        '--token',
        help='GitHub token. Defaults to GITHUB_TOKEN env var'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without creating issues'
    )

    args = parser.parse_args()

    # Get repo and token
    repo = args.repo or os.getenv('GITHUB_REPOSITORY')
    token = args.token or os.getenv('GITHUB_TOKEN')

    if not repo:
        print("ERROR: --repo not specified and GITHUB_REPOSITORY not set", file=sys.stderr)
        sys.exit(1)

    if not token and not args.dry_run:
        print("ERROR: --token not specified and GITHUB_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # Parse test results
    xml_path = Path(args.junit_xml)
    if not xml_path.exists():
        print(f"ERROR: Test results file not found: {xml_path}", file=sys.stderr)
        sys.exit(1)

    failures = parse_junit_xml(xml_path)

    # Create/update issues
    create_or_update_issues(failures, repo, token, args.dry_run)


if __name__ == '__main__':
    main()
