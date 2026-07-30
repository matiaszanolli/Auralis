#!/usr/bin/env python3
"""
Recompute the structural counts quoted in CLAUDE.md and
.claude/commands/_audit-common.md (analysis file count, registered routers,
test files, test functions, docs topic dirs) directly from the live tree.

CLAUDE.md and _audit-common.md each hand-maintain their own copy of these
numbers, which drift apart whenever one is edited without the other (#4982).
Run this before touching either file's counts and paste the printed values
into both — it is the single source of truth for what the numbers *should*
be, the same role sync_version.py plays for the version string.

Usage:
    python scripts/check_doc_counts.py
"""

import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def count_files(pattern: str, root: str) -> int:
    return len(list((PROJECT_ROOT / root).rglob(pattern)))


def count_registered_routers() -> int:
    routes_file = PROJECT_ROOT / "auralis-web/backend/config/routes.py"
    content = routes_file.read_text()
    return len(re.findall(r"app\.include_router\(", content))


def count_test_functions() -> int:
    result = subprocess.run(
        ["grep", "-rn", "def test_", str(PROJECT_ROOT / "tests"), "--include=*.py"],
        capture_output=True, text=True, check=False,
    )
    return len(result.stdout.splitlines())


def count_test_files() -> int:
    tests_dir = PROJECT_ROOT / "tests"
    names = {p for p in tests_dir.rglob("test_*.py")} | {p for p in tests_dir.rglob("*_test.py")}
    return len(names)


def count_docs_topic_dirs() -> int:
    docs_dir = PROJECT_ROOT / "docs"
    return len([p for p in docs_dir.iterdir() if p.is_dir()])


def main() -> None:
    counts = {
        "auralis/analysis/ .py files": count_files("*.py", "auralis/analysis"),
        "Registered routers": count_registered_routers(),
        "Test files": count_test_files(),
        "Test functions": count_test_functions(),
        "docs/ topic dirs": count_docs_topic_dirs(),
    }
    width = max(len(k) for k in counts)
    print("Live structural counts — paste into CLAUDE.md and _audit-common.md:\n")
    for label, value in counts.items():
        print(f"  {label:<{width}} {value}")


if __name__ == "__main__":
    main()
