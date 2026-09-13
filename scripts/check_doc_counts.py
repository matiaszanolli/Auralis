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

The test-function/test-file count (the fastest-moving numbers here — they
change on nearly every commit that touches tests/) gets the same kind of
active check via `--check-docs`: it re-parses the "~N test functions (M
files)" line out of CLAUDE.md and _audit-common.md and WARNS (never fails)
when either has drifted past a tolerance. This line drifted three times in a
row (#4685, #4982, #5045) despite two prior manual fixes, because nothing
re-checked it on a cadence; `.claude/commands/_audit-validate.sh` calls this
mode on every run so a stale count gets surfaced without gating anything.

Usage:
    python scripts/check_doc_counts.py               # print live counts + repo-count check
    python scripts/check_doc_counts.py --check-docs   # also WARN on stale test counts (exit 0 always)
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# How far the doc-quoted "~N test functions (M files)" line may drift from
# the live tree before --check-docs warns. Loose on purpose: these are the
# fastest-moving counts in the file (every commit that adds/removes a test
# changes them), so a tight threshold would warn on nearly every commit and
# train people to ignore the warning. 10% catches the kind of week-plus
# staleness that kept recurring (#4685, #4982, #5045), not routine drift.
TEST_COUNT_DRIFT_TOLERANCE = 0.10

TEST_COUNT_LINE_RE = re.compile(r"~?([\d,]+)\s+test functions\s+\(([\d,]+)\s+files\)")

DOCS_WITH_TEST_COUNTS = ["CLAUDE.md", ".claude/commands/_audit-common.md"]


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


def check_stale_test_counts(live_files: int, live_functions: int) -> list[str]:
    """WARN (never fail) when CLAUDE.md / _audit-common.md's "~N test
    functions (M files)" line has drifted from the live tree beyond
    TEST_COUNT_DRIFT_TOLERANCE. This exact line drifted three times in a row
    (#4685, #4982, #5045) because nothing re-checked it between manual
    fixes — this is that re-check, wired into _audit-validate.sh."""
    warnings = []
    for doc in DOCS_WITH_TEST_COUNTS:
        path = PROJECT_ROOT / doc
        if not path.exists():
            continue
        match = TEST_COUNT_LINE_RE.search(path.read_text())
        if not match:
            warnings.append(f"{doc}: no \"~N test functions (M files)\" line found to check")
            continue
        stated_functions = int(match.group(1).replace(",", ""))
        stated_files = int(match.group(2).replace(",", ""))
        for label, stated, live in (
            ("test functions", stated_functions, live_functions),
            ("test files", stated_files, live_files),
        ):
            if live == 0:
                continue
            drift = abs(live - stated) / live
            if drift > TEST_COUNT_DRIFT_TOLERANCE:
                warnings.append(
                    f"{doc}: says {stated} {label}, live is {live} "
                    f"({drift:.0%} drift, tolerance {TEST_COUNT_DRIFT_TOLERANCE:.0%})"
                )
    return warnings


def main() -> None:
    check_docs = "--check-docs" in sys.argv[1:]

    repo_count = count_repositories()
    test_files = count_test_files()
    test_functions = count_test_functions()
    counts = {
        "auralis/analysis/ .py files": count_files("*.py", "auralis/analysis"),
        "Registered routers": count_registered_routers(),
        "Test files": test_files,
        "Test functions": test_functions,
        "docs/ topic dirs": count_docs_topic_dirs(),
        "Library repositories": repo_count,
    }
    width = max(len(k) for k in counts)
    print("Live structural counts — paste into CLAUDE.md and _audit-common.md:\n")
    for label, value in counts.items():
        print(f"  {label:<{width}} {value}")

    stale_repos = check_stale_repository_counts(repo_count)
    if stale_repos:
        print("\nStale repository-count references in .claude/{agents,commands}/*.md:\n")
        for warning in stale_repos:
            print(f"  {warning}")
    else:
        print("\n.claude/{agents,commands}/*.md repository-count references are all current.")

    if check_docs:
        stale_tests = check_stale_test_counts(test_files, test_functions)
        if stale_tests:
            print("\nWARN: stale test-count references (non-blocking):\n")
            for warning in stale_tests:
                print(f"  WARN: {warning}")
        else:
            print("\nTest-count references in CLAUDE.md/_audit-common.md are current.")
    # Always exits 0 — this script informs, it never gates (the WARN-level
    # contract from #5045; the hard STRICT/RATCHET gates live in
    # _audit-validate.sh's own path-reference checks, not here).


if __name__ == "__main__":
    main()
