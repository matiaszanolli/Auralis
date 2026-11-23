"""The nightly slow lane gates on its own baseline file via --baseline (#6502).

slow-tests.yml was report-only: its pytest step ended in `|| true` and nothing compared the junit
report with a baseline, so a regression confined to the ~325 slow tests never failed a build. The
gate script now takes --baseline, and the workflow runs it against pytest-slow-baseline.json.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_pytest_baseline.py"


def _junit(path: Path, failing: list[str], passing: list[str]) -> None:
    cases = "".join(
        f'<testcase classname="{c}" name="{n}"><failure message="x"/></testcase>'
        for c, n in (f.split("::") for f in failing)
    ) + "".join(f'<testcase classname="{c}" name="{n}"/>' for c, n in (p.split("::") for p in passing))
    total = len(failing) + len(passing)
    path.write_text(f'<testsuites><testsuite tests="{total}" failures="{len(failing)}">{cases}</testsuite></testsuites>')


def _gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)


def test_a_slow_failure_missing_from_its_baseline_fails_the_gate(tmp_path):
    baseline = tmp_path / "slow-baseline.json"
    report = tmp_path / "slow.xml"
    _junit(report, [], ["tests.x::test_a", "tests.x::test_b"])
    assert _gate(str(report), "--baseline", str(baseline), "--update").returncode == 0
    assert json.loads(baseline.read_text())["failures"] == []

    _junit(report, ["tests.x::test_a"], ["tests.x::test_b"])
    result = _gate(str(report), "--baseline", str(baseline), "--strict-stale")

    assert result.returncode != 0
    assert "tests.x::test_a" in result.stdout + result.stderr


def test_the_nightly_workflow_runs_the_gate_on_the_tracked_slow_baseline():
    steps = yaml.safe_load((ROOT / ".github/workflows/slow-tests.yml").read_text())["jobs"]["pytest-slow"]["steps"]
    gate = next(s for s in steps if s.get("name") == "Check slow-test baseline")
    assert "--baseline pytest-slow-baseline.json" in gate["run"] and "--strict-stale" in gate["run"]
    assert json.loads((ROOT / "pytest-slow-baseline.json").read_text())["failures"] == []
