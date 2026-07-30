"""
pytest-baseline.json Missing-File Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #4739:
``check_pytest_baseline.py``'s ``load_baseline()`` used to call ``sys.exit(1)``
unconditionally whenever ``pytest-baseline.json`` was missing, regardless of
the actual test outcome — the deciding CI step failed on every run since the
file had never been committed. ``load_baseline()`` now degrades to an empty
baseline (fail only on an actual new failure) with a loud warning, so a future
accidental deletion of the baseline fails safe rather than failing always.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "check_pytest_baseline.py"
_spec = importlib.util.spec_from_file_location("check_pytest_baseline", _SCRIPT_PATH)
check_pytest_baseline = importlib.util.module_from_spec(_spec)
sys.modules["check_pytest_baseline"] = check_pytest_baseline
_spec.loader.exec_module(check_pytest_baseline)


@pytest.mark.regression
class TestLoadBaselineMissingFile:
    def test_missing_baseline_degrades_to_empty_set(self, tmp_path, monkeypatch, capsys):
        """A missing pytest-baseline.json must return an empty set (fixes #4739),
        not sys.exit(1) unconditionally."""
        monkeypatch.setattr(check_pytest_baseline, "BASELINE_PATH", tmp_path / "does-not-exist.json")

        result = check_pytest_baseline.load_baseline()

        assert result == set()
        assert "No baseline" in capsys.readouterr().err

    def test_missing_baseline_still_fails_on_a_real_new_failure(self, tmp_path, monkeypatch):
        """Degrading to an empty baseline must still fail the gate when the
        run has an actual failure — this is 'fail on any failure', not
        'always pass'."""
        monkeypatch.setattr(check_pytest_baseline, "BASELINE_PATH", tmp_path / "does-not-exist.json")

        junit_xml = tmp_path / "results.xml"
        junit_xml.write_text(
            '<testsuite tests="1" failures="1">'
            '<testcase classname="tests.test_x" name="test_y">'
            "<failure message=\"boom\"/></testcase>"
            "</testsuite>"
        )

        # main() reads argv via argparse; invoke it directly with sys.argv patched.
        monkeypatch.setattr(sys, "argv", ["check_pytest_baseline.py", str(junit_xml)])
        assert check_pytest_baseline.main() == 1

    def test_missing_baseline_passes_a_clean_run(self, tmp_path, monkeypatch):
        """A missing baseline plus zero failures must still exit 0 — the
        degraded empty baseline should not itself cause a false failure."""
        monkeypatch.setattr(check_pytest_baseline, "BASELINE_PATH", tmp_path / "does-not-exist.json")

        junit_xml = tmp_path / "results.xml"
        junit_xml.write_text('<testsuite tests="3" failures="0"></testsuite>')

        monkeypatch.setattr(sys, "argv", ["check_pytest_baseline.py", str(junit_xml)])
        assert check_pytest_baseline.main() == 0

    def test_existing_baseline_still_loads_normally(self, tmp_path, monkeypatch):
        """The happy path (baseline file present) must be unaffected."""
        baseline_path = tmp_path / "pytest-baseline.json"
        baseline_path.write_text('{"failures": ["tests.test_x::test_y"]}')
        monkeypatch.setattr(check_pytest_baseline, "BASELINE_PATH", baseline_path)

        assert check_pytest_baseline.load_baseline() == {"tests.test_x::test_y"}
