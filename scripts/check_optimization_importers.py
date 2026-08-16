#!/usr/bin/env python3
"""Pin the production-importer set of ``auralis/optimization/`` (#5142).

Why this exists
---------------
``.claude/commands/_audit-common.md`` — the protocol file every audit skill
loads first — used to assert:

    NO production code imports this package — the only importers are tests.
    Treat the remainder as unreferenced-by-runtime: a bug here has no
    user-visible blast radius, so cap severity accordingly.

That was false. ``auralis/core/hybrid_processor.py`` — the main DSP pipeline —
imports ``get_performance_optimizer`` and applies it at module-import time, so
the whole package is live engine code. The instruction told auditors to
downgrade any finding in it, which is severity suppression at the protocol
level: a thread-safety bug in the optimizer singleton would have been filed as
LOW tech debt.

The claim was hand-maintained prose, so it rotted silently. Fixing the wording
alone does not stop the next drift — this check does, by failing when the
importer set changes without the doc being updated with it.

Scope
-----
Deliberately stdlib-only and static (``ast``, no imports of the package under
test) so it can run in a lightweight CI job with no dependency install and no
built Rust module. The complementary *dynamic* assertion — that importing
``auralis.core.hybrid_processor`` really does pull
``auralis.optimization.performance_optimizer`` into ``sys.modules`` — lives in
``tests/test_optimization_is_live_5142.py``, which runs in the backend suite
where the dependencies exist.

Usage
-----
    python scripts/check_optimization_importers.py           # exit 1 on drift
    python scripts/check_optimization_importers.py --list    # print and exit 0
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

# Trees that ship. Anything under a tests dir is excluded — the point of the
# check is which *production* code reaches the package.
PRODUCTION_ROOTS = ("auralis", "auralis-web/backend")

PACKAGE = "optimization"

# The expected production importers, as (path, imported submodule).
#
# Keep this in lockstep with the "Optimization:" row of
# .claude/commands/_audit-common.md. Changing one without the other is exactly
# the drift this file exists to catch.
EXPECTED: dict[tuple[str, str], str] = {
    ("auralis/core/hybrid_processor.py", "performance_optimizer"): (
        "LIVE. Applied unconditionally at module-import time via "
        "_apply_module_optimizations(), so the PerformanceOptimizer singleton "
        "and everything it constructs is live on every mastering call."
    ),
    ("auralis/dsp/utils/spectral.py", "rust_integration"): (
        "DEAD BRANCH, intentionally listed. auralis/optimization/rust_integration.py "
        "does not exist; the ModuleNotFoundError is swallowed by an enclosing "
        "except Exception, so the Rust tempo fast path never runs (#5168). "
        "Listed rather than ignored so that creating the module — which would "
        "silently switch a production code path on — trips this check."
    ),
}


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


def is_test_path(rel: str) -> bool:
    parts = Path(rel).parts
    return any(p in {"tests", "test", "__tests__"} for p in parts) or Path(rel).name.startswith("test_")


def submodule_of(node: ast.ImportFrom, rel: str) -> str | None:
    """Return the optimization submodule this ImportFrom targets, if any.

    Handles both the absolute form (``from auralis.optimization.x import y``)
    and the relative forms used in-tree (``from ..optimization.x import y``).
    ``node.module`` is None for a bare ``from . import x``, which never names
    the package and is skipped.
    """
    module = node.module
    if not module:
        return None
    parts = module.split(".")
    if PACKAGE not in parts:
        return None
    idx = parts.index(PACKAGE)
    # `from ..optimization import performance_optimizer` names the submodule in
    # the alias list rather than the module path.
    if idx + 1 < len(parts):
        return parts[idx + 1]
    return node.names[0].name if node.names else PACKAGE


def scan(root: Path) -> dict[tuple[str, str], None]:
    found: dict[tuple[str, str], None] = {}
    for sub in PRODUCTION_ROOTS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            # The package's own internals import each other; not importers.
            if rel.startswith("auralis/optimization/") or is_test_path(rel):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    name = submodule_of(node, rel)
                    if name:
                        found[(rel, name)] = None
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if PACKAGE in parts:
                            idx = parts.index(PACKAGE)
                            name = parts[idx + 1] if idx + 1 < len(parts) else PACKAGE
                            found[(rel, name)] = None
    return found


def main() -> int:
    root = repo_root()
    found = set(scan(root))
    expected = set(EXPECTED)

    if "--list" in sys.argv[1:]:
        for path, name in sorted(found):
            print(f"{path} -> auralis.optimization.{name}")
        return 0

    added = sorted(found - expected)
    removed = sorted(expected - found)

    if not added and not removed:
        print(f"OK: auralis/optimization/ production importers unchanged ({len(found)} known).")
        return 0

    print("FAIL: the production-importer set of auralis/optimization/ changed (#5142).")
    print()
    for path, name in added:
        print(f"  NEW importer: {path} -> auralis.optimization.{name}")
    for path, name in removed:
        print(f"  GONE: {path} -> auralis.optimization.{name}")
        print(f"        was: {EXPECTED[(path, name)]}")
    print()
    print("This set is documented in the 'Optimization:' row of")
    print(".claude/commands/_audit-common.md, which tells auditors what severity")
    print("to apply to findings in that package. Update BOTH that row and the")
    print("EXPECTED table in this script, in the same change.")
    print()
    print("In particular: if the package ever genuinely loses all production")
    print("importers, the row must stop saying LIVE ENGINE CODE — and if it")
    print("gains one, it must not be re-marked test-only.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
