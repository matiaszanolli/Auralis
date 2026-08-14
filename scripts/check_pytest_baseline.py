#!/usr/bin/env python3
"""Ratchet gate for the pytest suite (#4562).

No GitHub Actions workflow has ever run pytest. Five tracked workflow files sat
in ``.github/workflows.backup/`` with a README describing them, in the present
tense, as the active pipeline that ran backend tests, linting and Codecov upload
on every push and PR — none of which GitHub executes, since it only runs
``.github/workflows/``. That false confidence is a large part of why a broken
``tests/conftest.py`` and a drifted dependency manifest could sit in the repo
undetected.

Demanding a green suite on day one would mean the gate is disabled on day one:
the suite carries a substantial pre-existing failure baseline. So this compares
the current run against a checked-in baseline and fails only on *new* failures.
The baseline may shrink, never grow.

This is the pytest counterpart of ``auralis-web/frontend/scripts/check-test-baseline.mjs``
(#4640); the two deliberately share a design so there is one idea to learn.

Usage::

    python scripts/check_pytest_baseline.py <junit.xml>                 # verify
    python scripts/check_pytest_baseline.py <junit.xml> --update        # rewrite baseline
    python scripts/check_pytest_baseline.py <junit.xml> --strict-stale  # also fail on stale entries

Stale entries are the other half of the ratchet (#5091): a baselined test that
starts passing but keeps its entry silently re-permits that exact failure, so
the test can regress and CI stays green. 69 such entries had accumulated in a
27-file sample before this was reported. Staleness is always *reported*;
``--strict-stale`` makes it *fail*, and counts only tests actually present in
the report so a scoped run cannot trip it.

Exit codes: 0 = no new failures, 1 = new failures (or unusable input),
1 = stale entries when ``--strict-stale`` is set.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "pytest-baseline.json"

# Printed when a large number of entries changes, to keep CI logs readable.
_MAX_LISTED = 25


def _die(message: str) -> NoReturn:
    print(f"✖ {message}", file=sys.stderr)
    sys.exit(1)


def read_results(path: Path) -> ET.Element:
    """Parse the JUnit XML pytest wrote, failing loudly if it is unusable."""
    try:
        tree = ET.parse(path)
    except FileNotFoundError:
        _die(
            f"Could not read pytest results at {path}.\n"
            "  The suite most likely crashed or timed out before writing a report."
        )
    except ET.ParseError as err:
        _die(f"pytest results at {path} are not valid XML: {err}")

    root = tree.getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    if not suites:
        _die(f"pytest results at {path} contain no testsuite element.")

    total = sum(int(s.get("tests", 0)) for s in suites)
    # A run that collected nothing is a broken runner, not a green suite.
    if total == 0:
        _die("pytest reported 0 collected tests — treating as a failed run.")
    return root


def collect_failures(root: ET.Element) -> set[str]:
    """Identify each failure by ``<classname>::<test name>``.

    Names rather than a bare count: a count-only baseline goes green when one
    test starts failing while another is deleted. ``classname`` is pytest's
    dotted module path (plus class), which is identical on a developer machine
    and on a CI runner — unlike an absolute file path.
    """
    failures: set[str] = set()
    for case in root.iter("testcase"):
        # `error` covers collection/fixture errors, which never produce a
        # `failure` element and would otherwise slip through entirely.
        if case.find("failure") is not None or case.find("error") is not None:
            classname = case.get("classname", "")
            name = case.get("name", "<unknown>")
            failures.add(f"{classname}::{name}" if classname else name)
    return failures


def collect_all_test_ids(root: ET.Element) -> set[str]:
    """Every test present in the report, passing or not.

    Needed to tell a baseline entry that *ran and passed* (genuinely stale)
    apart from one that simply was not part of this run — a scoped invocation,
    a renamed or deleted test, or a file the workflow ``--ignore``s. Subtracting
    failures from the baseline alone conflates the two, which would make the
    strict mode below fail on any partial artifact.
    """
    ids: set[str] = set()
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "<unknown>")
        ids.add(f"{classname}::{name}" if classname else name)
    return ids


def counts(root: ET.Element) -> tuple[int, int]:
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total = sum(int(s.get("tests", 0)) for s in suites)
    bad = sum(
        int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites
    )
    return total, bad


def load_baseline() -> set[str]:
    try:
        payload = json.loads(BASELINE_PATH.read_text())
    except FileNotFoundError:
        # Degrade to an empty baseline rather than hard-failing every run
        # unconditionally (#4739): a missing file should fail on any actual
        # test failure, not fail regardless of the suite's real outcome.
        print(
            f"⚠ No baseline at {BASELINE_PATH} — treating as empty (fail on "
            "any failure).\n"
            "  Generate one with: python scripts/check_pytest_baseline.py <junit.xml> --update",
            file=sys.stderr,
        )
        return set()
    except json.JSONDecodeError as err:
        _die(f"Baseline at {BASELINE_PATH} is not valid JSON: {err}")
    return set(payload.get("failures", []))


def write_baseline(current: set[str], total: int, bad: int) -> None:
    payload = {
        "_comment": (
            "Known-failing pytest tests (#4562). CI fails on any failure NOT "
            "listed here. Regenerate with: "
            "python scripts/check_pytest_baseline.py <junit.xml> --update"
        ),
        "generatedFrom": {"totalTests": total, "failedTests": bad},
        "failures": sorted(current),
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"✔ Baseline updated: {len(current)} known failures.")


def _listing(ids: list[str]) -> str:
    shown = "\n".join(f"    {i}" for i in ids[:_MAX_LISTED])
    if len(ids) > _MAX_LISTED:
        shown += f"\n    ... and {len(ids) - _MAX_LISTED} more"
    return shown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="pytest --junitxml output")
    parser.add_argument(
        "--update", action="store_true", help="rewrite the baseline from this run"
    )
    parser.add_argument(
        "--strict-stale",
        action="store_true",
        help=(
            "also fail when a baselined test ran and PASSED (a stale entry). "
            "Only counts tests actually present in this report, so a scoped "
            "run cannot trip it."
        ),
    )
    args = parser.parse_args()

    root = read_results(args.results)
    current = collect_failures(root)
    total, bad = counts(root)

    if args.update:
        write_baseline(current, total, bad)
        return 0

    baseline = load_baseline()
    present = collect_all_test_ids(root)
    added = sorted(current - baseline)
    # Split what the old code lumped together as "no longer fails" (#5091).
    # A baselined test that ran and passed is stale and must be removed;
    # one absent from the report was simply not run and says nothing.
    stale = sorted((baseline & present) - current)
    not_run = sorted(baseline - present)

    print(
        f"pytest: {total} collected, {len(current)} failing "
        f"(baseline allows {len(baseline)})."
    )

    if stale:
        print(f"\n✔ {len(stale)} baseline entry(ies) ran and PASSED — stale:")
        print(_listing(stale))
        print(
            "  Each one silently re-permits that exact failure: the test can "
            "regress and CI stays green.\n"
            "  Remove them, or regenerate: "
            "python scripts/check_pytest_baseline.py <junit.xml> --update"
        )

    if not_run:
        print(
            f"\nℹ {len(not_run)} baseline entry(ies) were not in this report "
            "(scoped run, --ignore'd file, or renamed/deleted test)."
        )
        print(_listing(not_run))
        print("  Not treated as stale — this report cannot prove they pass.")

    if added:
        print(f"\n✖ {len(added)} NEW test failure(s) not in the baseline:\n", file=sys.stderr)
        print(_listing(added), file=sys.stderr)
        print(
            "\nFix them, or — only if the failure is genuinely pre-existing and "
            "was merely unmasked — regenerate the baseline and explain why in "
            "the PR.",
            file=sys.stderr,
        )
        return 1

    if stale and args.strict_stale:
        print(
            f"\n✖ --strict-stale: {len(stale)} baselined test(s) now pass. "
            "The ratchet may shrink, never grow — tighten it.",
            file=sys.stderr,
        )
        return 1

    print("\n✔ No new test failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
