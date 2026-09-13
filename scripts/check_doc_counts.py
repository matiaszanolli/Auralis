#!/usr/bin/env python3
"""
Recompute the structural counts quoted in CLAUDE.md and
.claude/commands/_audit-common.md (analysis file count, registered routers,
test files, test functions, docs topic dirs, library repository count)
directly from the live tree.

CLAUDE.md and _audit-common.md each hand-maintain their own copy of these
numbers, which drift apart whenever one is edited without the other (#4982).
Run this before touching either file's counts and paste the printed values
into both — it is the single source of truth for what the numbers *should*
be, the same role sync_version.py plays for the version string.

The repository count additionally gets an active check (not just a printed
value to paste in): `.claude/agents/*.md` is scanned for "N repositor(y|ies)"
references and any that diverge from the live count are flagged, since that
directory drifted silently for weeks after #4997 deleted a repository (#5044).

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


def count_repositories() -> int:
    """Live library repository count.

    `*_repository.py` naturally excludes `base.py`/`factory.py`/`__init__.py`
    and the mixin/split-helper files (`track_repository_lifecycle.py`,
    `playlist_crud_mixin.py`, `fingerprint_shared.py`, ...) that implement
    pieces of a repository but aren't one themselves (#5044).
    """
    repo_dir = PROJECT_ROOT / "auralis/library/repositories"
    return len(list(repo_dir.glob("*_repository.py")))


def check_stale_repository_counts(live_count: int) -> list[str]:
    """Flag `.claude/agents/*.md` and `.claude/commands/*.md` files whose
    stated repository count has drifted from the live tree (#5044 — #4997
    deleted a repository and six references across three skill/agent files
    went stale for weeks with nothing to catch it)."""
    pattern = re.compile(r"(\d+)\s+repositor(?:y|ies)")
    warnings = []
    paths = sorted((PROJECT_ROOT / ".claude/agents").glob("*.md")) + sorted(
        (PROJECT_ROOT / ".claude/commands").glob("*.md")
    )
    for path in paths:
        content = path.read_text()
        for match in pattern.finditer(content):
            stated = int(match.group(1))
            if stated != live_count:
                line_no = content.count("\n", 0, match.start()) + 1
                warnings.append(
                    f"{path.relative_to(PROJECT_ROOT)}:{line_no} says "
                    f"{stated} repositories, live count is {live_count}"
                )
    return warnings


def main() -> None:
    repo_count = count_repositories()
    counts = {
        "auralis/analysis/ .py files": count_files("*.py", "auralis/analysis"),
        "Registered routers": count_registered_routers(),
        "Test files": count_test_files(),
        "Test functions": count_test_functions(),
        "docs/ topic dirs": count_docs_topic_dirs(),
        "Library repositories": repo_count,
    }
    width = max(len(k) for k in counts)
    print("Live structural counts — paste into CLAUDE.md and _audit-common.md:\n")
    for label, value in counts.items():
        print(f"  {label:<{width}} {value}")

    stale = check_stale_repository_counts(repo_count)
    if stale:
        print("\nStale repository-count references in .claude/{agents,commands}/*.md:\n")
        for warning in stale:
            print(f"  {warning}")
    else:
        print("\n.claude/{agents,commands}/*.md repository-count references are all current.")


if __name__ == "__main__":
    main()
