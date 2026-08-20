#!/usr/bin/env python3
"""Ratchet gate for tests whose only assertions are ``X is not None`` (#5154).

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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"
BASELINE_PATH = REPO_ROOT / "weak-assertions-baseline.json"


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


def find_offenders(tests_root: Path = TESTS_ROOT) -> dict[str, int]:
    """Every sole-`is not None` test under ``tests_root``."""
    offenders: dict[str, int] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        offenders.update(scan_file(path))
    return offenders


def load_baseline() -> set[str]:
    try:
        return set(json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["offenders"])
    except FileNotFoundError:
        return set()
    except (json.JSONDecodeError, KeyError) as err:
        print(f"x Could not read {BASELINE_PATH.name}: {err}", file=sys.stderr)
        sys.exit(1)


def write_baseline(offenders: dict[str, int]) -> None:
    payload = {
        "_comment": (
            "Tests whose only assertions are `X is not None` (#5154). A test listed "
            "here is known-weak; CI fails on any offender NOT listed. The list may "
            "shrink, never grow. Regenerate with: "
            "python scripts/check_weak_assertions.py --update"
        ),
        "count": len(offenders),
        "offenders": sorted(offenders),
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("--list", action="store_true", help="print current offenders")
    args = parser.parse_args()

    offenders = find_offenders()

    if args.list:
        for name, count in sorted(offenders.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"{count:3d}  {name}")
        print(f"\n{len(offenders)} test(s); "
              f"{sum(1 for c in offenders.values() if c > 1)} with more than one assertion")
        return 0

    if args.update:
        write_baseline(offenders)
        print(f"Baseline rewritten: {BASELINE_PATH.name} ({len(offenders)} entries).")
        print("Commit it. The count may shrink in future, never grow.")
        return 0

    baseline = load_baseline()
    current = set(offenders)
    new = sorted(current - baseline)
    fixed = sorted(baseline - current)

    print(f"Sole-`is not None` tests: {len(current)} (baseline allows {len(baseline)}).")

    if fixed:
        print(f"\n+ {len(fixed)} baseline entry(ies) no longer weak:")
        for name in fixed[:20]:
            print(f"    {name}")
        if len(fixed) > 20:
            print(f"    ... and {len(fixed) - 20} more")
        print("  Shrink the baseline: python scripts/check_weak_assertions.py --update")

    if new:
        print(f"\nx {len(new)} test(s) assert only `is not None` and are not baselined:")
        for name in new:
            print(f"    {name}  ({offenders[name]} assertion(s))")
        print("\n  Assert the value the test is named for, not merely that it exists.")
        print("  The baseline may shrink, never grow — do not add these to it.")
        return 1

    print("OK: no new weak-assertion tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
