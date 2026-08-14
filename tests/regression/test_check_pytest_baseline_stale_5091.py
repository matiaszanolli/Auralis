"""
Stale-baseline-entry detection (#5091).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A baselined test that starts passing but keeps its entry silently re-permits
that exact failure: the test can regress and CI stays green because the failure
is already "allowed". 69 such entries had accumulated across a 27-file sample.

The script always reported these ("N baseline failure(s) no longer fail"), but
computed them as ``baseline - failures`` — which also swept in every baselined
test that simply was not part of the run (a scoped invocation, an ``--ignore``d
file, a renamed or deleted test). That conflation is why the number was
advisory-only: it could not be trusted enough to fail on.

Now the two are separated — a baseline entry is stale only if it is *present in
the report* and not failing — and ``--strict-stale`` turns the genuine ones into
a non-zero exit.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "check_pytest_baseline.py"
_spec = importlib.util.spec_from_file_location("check_pytest_baseline_stale", _SCRIPT_PATH)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_pytest_baseline_stale"] = gate
_spec.loader.exec_module(gate)


def _junit(tmp_path, cases):
    """cases: list of (classname, name, failed)."""
    body = ""
    for classname, name, failed in cases:
        inner = '<failure message="boom"/>' if failed else ""
        body += f'<testcase classname="{classname}" name="{name}">{inner}</testcase>'
    failures = sum(1 for _, _, f in cases if f)
    path = tmp_path / "results.xml"
    path.write_text(
        f'<testsuite tests="{len(cases)}" failures="{failures}">{body}</testsuite>'
    )
    return path


def _baseline(tmp_path, monkeypatch, entries):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"failures": sorted(entries)}))
    monkeypatch.setattr(gate, "BASELINE_PATH", path)
    return path


@pytest.mark.regression
class TestCollectAllTestIds:
    def test_includes_passing_and_failing(self, tmp_path):
        root = gate.read_results(
            _junit(tmp_path, [("m", "passes", False), ("m", "fails", True)])
        )
        assert gate.collect_all_test_ids(root) == {"m::passes", "m::fails"}

    def test_failures_are_a_subset(self, tmp_path):
        root = gate.read_results(
            _junit(tmp_path, [("m", "passes", False), ("m", "fails", True)])
        )
        assert gate.collect_failures(root) <= gate.collect_all_test_ids(root)


@pytest.mark.regression
class TestStaleDetection:
    def test_passing_baselined_test_is_reported_stale(
        self, tmp_path, monkeypatch, capsys
    ):
        _baseline(tmp_path, monkeypatch, {"m::was_failing"})
        results = _junit(tmp_path, [("m", "was_failing", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results)])

        assert gate.main() == 0  # reported, but not fatal by default
        out = capsys.readouterr().out
        assert "stale" in out.lower()
        assert "m::was_failing" in out

    def test_strict_stale_fails_on_it(self, tmp_path, monkeypatch):
        _baseline(tmp_path, monkeypatch, {"m::was_failing"})
        results = _junit(tmp_path, [("m", "was_failing", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results), "--strict-stale"])

        assert gate.main() == 1

    def test_still_failing_baselined_test_is_not_stale(self, tmp_path, monkeypatch):
        _baseline(tmp_path, monkeypatch, {"m::still_failing"})
        results = _junit(tmp_path, [("m", "still_failing", True)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results), "--strict-stale"])

        assert gate.main() == 0


@pytest.mark.regression
class TestNotRunIsNotStale:
    """The distinction that makes --strict-stale safe to enable."""

    def test_absent_entry_does_not_fail_strict_mode(self, tmp_path, monkeypatch):
        """A scoped run must not look like 200 fixed tests."""
        _baseline(tmp_path, monkeypatch, {"other::not_in_this_run"})
        results = _junit(tmp_path, [("m", "unrelated", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results), "--strict-stale"])

        assert gate.main() == 0

    def test_absent_entry_is_reported_separately(self, tmp_path, monkeypatch, capsys):
        _baseline(tmp_path, monkeypatch, {"other::not_in_this_run"})
        results = _junit(tmp_path, [("m", "unrelated", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results)])

        gate.main()
        out = capsys.readouterr().out
        assert "not in this report" in out
        assert "other::not_in_this_run" in out
        assert "Not treated as stale" in out

    def test_mixed_report_separates_the_two(self, tmp_path, monkeypatch, capsys):
        _baseline(tmp_path, monkeypatch, {"m::now_passes", "gone::deleted_test"})
        results = _junit(tmp_path, [("m", "now_passes", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results), "--strict-stale"])

        assert gate.main() == 1  # only the genuinely-stale one is fatal
        out = capsys.readouterr().out
        stale_section = out.split("not in this report")[0]
        assert "m::now_passes" in stale_section
        assert "gone::deleted_test" not in stale_section


@pytest.mark.regression
class TestNewFailuresStillTakePrecedence:
    def test_new_failure_fails_regardless_of_strict_stale(self, tmp_path, monkeypatch):
        _baseline(tmp_path, monkeypatch, set())
        results = _junit(tmp_path, [("m", "brand_new_failure", True)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results)])

        assert gate.main() == 1

    def test_clean_run_against_accurate_baseline_passes_strict(
        self, tmp_path, monkeypatch
    ):
        _baseline(tmp_path, monkeypatch, {"m::known"})
        results = _junit(tmp_path, [("m", "known", True), ("m", "fine", False)])
        monkeypatch.setattr(sys, "argv", ["gate", str(results), "--strict-stale"])

        assert gate.main() == 0
