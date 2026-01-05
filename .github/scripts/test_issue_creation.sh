#!/bin/bash
# Test script for auto-issue creation
# Run this locally to test the issue creation workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🧪 Testing Auto-Issue Creation Script"
echo "====================================="
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
if ! python3 -c "import github" 2>/dev/null; then
    echo "❌ PyGithub not installed. Installing..."
    pip install PyGithub
fi

# Run tests to generate JUnit XML
echo ""
echo "🔬 Running tests to generate test results..."
cd "$PROJECT_ROOT"

# Run a subset of tests that might fail
python -m pytest tests/auralis/analysis/fingerprint/ -v \
    --junitxml=test-results-sample.xml \
    --tb=short \
    -x || true  # Continue even if tests fail

if [ ! -f test-results-sample.xml ]; then
    echo "❌ No test results generated. Creating dummy test results for demo..."

    # Create a dummy JUnit XML with a fake failure for testing
    cat > test-results-sample.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1" time="0.123">
    <testcase classname="tests.test_example" name="test_example_failure" time="0.123" file="tests/test_example.py">
      <failure message="AssertionError: Test failed on purpose">
def test_example_failure():
&gt;   assert False, "This is a test failure for issue creation"
E   AssertionError: This is a test failure for issue creation

tests/test_example.py:42: AssertionError
      </failure>
    </testcase>
  </testsuite>
</testsuites>
EOF
fi

# Test in dry-run mode
echo ""
echo "🏃 Testing issue creation in DRY-RUN mode..."
echo ""
python "$SCRIPT_DIR/create_test_issues.py" \
    --junit-xml test-results-sample.xml \
    --repo "${GITHUB_REPOSITORY:-matiaszanolli/Auralis}" \
    --dry-run

echo ""
echo "✅ Dry-run test completed!"
echo ""
echo "Next steps:"
echo "  1. Review the output above to see what issues would be created"
echo "  2. To create actual issues (CAUTION: this will create real issues!):"
echo "     export GITHUB_TOKEN='your_token_here'"
echo "     python .github/scripts/create_test_issues.py \\"
echo "       --junit-xml test-results-sample.xml \\"
echo "       --repo matiaszanolli/Auralis"
echo ""
echo "  3. To test with your own test results:"
echo "     pytest tests/path/to/tests/ --junitxml=my-results.xml"
echo "     python .github/scripts/create_test_issues.py \\"
echo "       --junit-xml my-results.xml \\"
echo "       --repo matiaszanolli/Auralis \\"
echo "       --dry-run"
echo ""

# Cleanup
rm -f test-results-sample.xml
