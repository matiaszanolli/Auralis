#!/usr/bin/env python3
"""Ratchet gates for tests that assert (almost) nothing (#5154, #5807).

Two defects, one script, one baseline each:

* default mode — tests whose *only* assertions are ``X is not None`` (#5154);
* ``--zero`` mode — ``test_*`` functions with no assertion of any kind (#5807):
  no ``assert``, no ``pytest.raises``/``warns``, no ``assert*``/``check*``/
  ``verify*``/``expect*`` call. A body that ends in a comment ("this test
  documents expected behavior") is green against any defect.

The rest of this docstring describes the default mode; ``--zero`` works the
same way against ``zero-assertions-baseline.json``.

A test function that asserts nothing but non-nullness is green against almost
any defect: ``test_sql_injection_in_title`` passed whether or not the injection
succeeded, and a 4-assert E2E metadata test passed against an extractor
returning the wrong value for every field.

#4049 (31 tests) and #4257 (56 tests across 32 files) both fixed instances of
this pattern and both closed without adding a gate, so the count regrew to 57.
This is that gate.

Usage:
    python scripts/check_weak_assertions.py            # verify
    python scripts/check_weak_assertions.py --update   # shrink the baseline
    python scripts/check_weak_assertions.py --list     # print current offenders
    python scripts/check_weak_assertions.py --zero ...  # same, for zero-assertion tests

Exit codes: 0 = no offender outside the baseline, 1 = new offenders (or a
baseline that could not be read).

The baseline lists offenders by ``path::test_name`` rather than as a bare
count, matching ``pytest-baseline.json`` and the frontend's
``test-baseline.json``: a count-only baseline goes green when one test is
strengthened and another regresses. It may shrink, never grow.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"
BASELINE_PATH = REPO_ROOT / "weak-assertions-baseline.json"
ZERO_BASELINE_PATH = REPO_ROOT / "zero-assertions-baseline.json"

_ASSERTION_CALL_PREFIXES = ("assert", "check", "verify", "expect")
_ASSERTING_PYTEST_CALLS = {"raises", "warns", "deprecated_call", "fail", "skip", "xfail", "importorskip"}


def _is_not_none_assert(node: ast.Assert) -> bool:
    """True for exactly ``assert X is not None`` (with or without a message)."""
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


def scan_file(path: Path) -> dict[str, int]:
    """Map ``path::test_name`` -> assertion count for one test module.

    A test qualifies when it has at least one assertion and *every* assertion
    is ``is not None``. A test with no assertions at all is a different defect
    (see #4246) and is deliberately not reported here.

    Kept separate from :func:`find_offenders` so the conftest hook can scan
    exactly the files a session collected instead of re-walking the tree once
    per file.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}
    try:
        rel = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()

    offenders: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue
        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        if asserts and all(_is_not_none_assert(a) for a in asserts):
            offenders[f"{rel}::{node.name}"] = len(asserts)
    return offenders


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_fixture_or_skipped(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Fixtures named ``test_*`` and tests that are skipped/xfailed outright."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name in {"fixture", "skip", "skipif", "xfail"}:
            return True
    return False


def _asserts_something(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call):
            name = _call_name(child)
            if name in _ASSERTING_PYTEST_CALLS:
                return True
            if name.lstrip("_").lower().startswith(_ASSERTION_CALL_PREFIXES):
                return True
    return False


def scan_file_zero(path: Path) -> dict[str, int]:
    """Map ``path::test_name`` -> 0 for each test that asserts nothing at all.

    Fixtures that happen to be called ``test_*`` and tests marked skip/xfail are
    not reported: the first are not tests, and an unconditional skip is the
    business of the skip-accountability ratchet (#4691), not this one.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}
    try:
        rel = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()

    offenders: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test") or _is_fixture_or_skipped(node):
            continue
        if not _asserts_something(node):
            offenders[f"{rel}::{node.name}"] = 0
    return offenders


def find_offenders(
    tests_root: Path = TESTS_ROOT, scan: Callable[[Path], dict[str, int]] = scan_file
) -> dict[str, int]:
    """Every offending test under ``tests_root`` according to ``scan``."""
    offenders: dict[str, int] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        offenders.update(scan(path))
    return offenders


def load_baseline(path: Path = BASELINE_PATH) -> set[str]:
    try:
        return set(json.loads(path.read_text(encoding="utf-8"))["offenders"])
    except FileNotFoundError:
        return set()
    except (json.JSONDecodeError, KeyError) as err:
        print(f"x Could not read {path.name}: {err}", file=sys.stderr)
        sys.exit(1)


def write_baseline(offenders: dict[str, int], path: Path = BASELINE_PATH, zero: bool = False) -> None:
    what = (
        "Tests with no assertion of any kind (#5807)" if zero
        else "Tests whose only assertions are `X is not None` (#5154)"
    )
    payload = {
        "_comment": (
            f"{what}. A test listed here is known-weak; CI fails on any offender NOT "
            "listed. The list may shrink, never grow. Regenerate with: "
            f"python scripts/check_weak_assertions.py{' --zero' if zero else ''} --update"
        ),
        "count": len(offenders),
        "offenders": sorted(offenders),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("--list", action="store_true", help="print current offenders")
    parser.add_argument(
        "--zero", action="store_true",
        help="check tests with no assertion at all instead of sole-`is not None` tests",
    )
    args = parser.parse_args()

    baseline_path = ZERO_BASELINE_PATH if args.zero else BASELINE_PATH
    offenders = find_offenders(scan=scan_file_zero if args.zero else scan_file)
    label = "Zero-assertion" if args.zero else "Sole-`is not None`"
    advice = (
        "Assert the observable the docstring promises, or delete the test."
        if args.zero else "Assert the value the test is named for, not merely that it exists."
    )

    if args.list:
        for name, count in sorted(offenders.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"{count:3d}  {name}")
        print(f"\n{len(offenders)} test(s); "
              f"{sum(1 for c in offenders.values() if c > 1)} with more than one assertion")
        return 0

    if args.update:
        write_baseline(offenders, baseline_path, zero=args.zero)
        print(f"Baseline rewritten: {baseline_path.name} ({len(offenders)} entries).")
        print("Commit it. The count may shrink in future, never grow.")
        return 0

    baseline = load_baseline(baseline_path)
    current = set(offenders)
    new = sorted(current - baseline)
    fixed = sorted(baseline - current)

    print(f"{label} tests: {len(current)} (baseline allows {len(baseline)}).")

    if fixed:
        print(f"\n+ {len(fixed)} baseline entry(ies) no longer weak:")
        for name in fixed[:20]:
            print(f"    {name}")
        if len(fixed) > 20:
            print(f"    ... and {len(fixed) - 20} more")
        print(f"  Shrink the baseline: python scripts/check_weak_assertions.py{' --zero' if args.zero else ''} --update")

    if new:
        what = "assert nothing" if args.zero else "assert only `is not None`"
        print(f"\nx {len(new)} test(s) {what} and are not baselined:")
        for name in new:
            print(f"    {name}" if args.zero else f"    {name}  ({offenders[name]} assertion(s))")
        print(f"\n  {advice}")
        print("  The baseline may shrink, never grow — do not add these to it.")
        return 1

    print("OK: no new zero-assertion tests." if args.zero else "OK: no new weak-assertion tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
