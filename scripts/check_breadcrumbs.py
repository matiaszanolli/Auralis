#!/usr/bin/env python3
"""Fail on new 'was removed/deleted in #NNNN' breadcrumb comments (#6257).

History-narrating comments that cite the deleting issue ("X was removed in
#1234") regrew six times after manual sweeps (#4088, #4293, #4649, #5034,
#5820, and the 2026-10-22 audit) because nothing gated them. The git log
already carries this history; a comment may only carry a present-tense
constraint ("Do not re-add X: reason"), which this pattern does not match.

Checked roots: auralis/, auralis-web/backend/, auralis-web/frontend/src/,
vendor/auralis-dsp/src/.

Usage:
    python scripts/check_breadcrumbs.py [--root REPO_ROOT]

Exit codes: 0 = no breadcrumbs, 1 = at least one found (printed).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    "auralis",
    "auralis-web/backend",
    "auralis-web/frontend/src",
    "vendor/auralis-dsp/src",
)
SCAN_SUFFIXES = {".py", ".rs", ".ts", ".tsx", ".js", ".jsx"}

# The breadcrumb form: past tense + deletion verb + the deleting issue ref.
# Requires the #NNN on the same line, so behavioral docstrings ("True if
# track was removed") and constraint comments ("Do not re-add X") never match.
BREADCRUMB = re.compile(
    r"\b(?:was|were|been)\s+(?:removed|deleted|dropped|retired)\s+"
    r"(?:in|by|with)\s+#\d+",
    re.IGNORECASE,
)

# Files whose matches are accepted pending cleanup; shrink, never grow.
BASELINE: set[tuple[str, int]] = set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="repository root"
    )
    args = parser.parse_args()
    root: Path = args.root

    offenders: list[tuple[str, int, str]] = []
    for rel in SCAN_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SCAN_SUFFIXES or not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            relpath = str(path.relative_to(root))
            for lineno, line in enumerate(lines, start=1):
                if BREADCRUMB.search(line) and (relpath, lineno) not in BASELINE:
                    offenders.append((relpath, lineno, line.strip()))

    if offenders:
        print("Breadcrumb comments found (delete them; the git log has the history):")
        for relpath, lineno, line in offenders:
            print(f"  {relpath}:{lineno}: {line[:100]}")
        return 1
    print("Breadcrumbs: none found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
