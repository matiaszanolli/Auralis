#!/usr/bin/env python3
"""Fail on 'was removed/deleted in #NNNN' breadcrumbs and file:LINE anchors.

History-narrating comments that cite the deleting issue ("X was removed in
#1234") regrew six times after manual sweeps (#4088, #4293, #4649, #5034,
#5820, and the 2026-10-22 audit) because nothing gated them. The git log
already carries this history; a comment may only carry a present-tense
constraint ("Do not re-add X: reason"), which these patterns do not match.

#6680 widened the net after the gate passed with 19 narrations in place:
past-tense phrasings beyond "was removed in #N" ("went with #N", "is retired
(#N)", "now-deleted ... #N", "gone, see #N", "removed following #N"), and a
phrase wrapped across a line break ("was\n# removed in #N"). The wider forms
apply to source files only; tests keep only the original pattern, since a
test docstring legitimately records which issue removed what it guards.

It also rejects ``file.py:123`` line anchors in source (#6675): they rot as
soon as the cited file changes. Cite a symbol (``module.function``) instead,
the rule #6248 already applies to the docs.

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

# Wider past-tense narration forms, applied to non-test source only (#6680).
# A bare "is gone (#N)" is deliberately absent: it also describes runtime
# state ("the entry is gone (#5082)").
NARRATION = re.compile(
    "|".join(
        (
            r"\b(?:was|were|been)\s+(?:removed|deleted|retired|gone)\s*\(#\d+",
            r"\b(?:is|are)\s+retired\b[^\n#]{0,20}#\d+",
            r"\bwent\s+(?:with|away)\b[^\n]{0,60}#\d+",
            r"\bwent\s+in\s+#\d+",
            r"\bwent\s*\(#\d+",
            r"\bnow-deleted\b[^\n]{0,40}#\d+",
            r"\bdeleted here\b[^\n]{0,10}#\d+",
            r"\bgone,?\s+see\s+#\d+",
            r"\b(?:removed|deleted)\s+following\s+#\d+",
        )
    ),
    re.IGNORECASE,
)

# Leading comment/docstring markers stripped from a continuation line before
# it is joined to the line above.
COMMENT_LEAD = re.compile(r"^\s*(?:#+|//+|/?\*+)?\s*")

# A source-file reference pinned to a line number, e.g. `stream.py:597` or
# `enhancement.ts:71-78` (#6675).
LINE_ANCHOR = re.compile(r"\b[\w./-]+\.(?:py|rs|tsx?|jsx?):\d+")

# Files whose matches are accepted pending cleanup; shrink, never grow.
BASELINE: set[tuple[str, int]] = set()


def _is_test_file(relpath: str) -> bool:
    name = relpath.rsplit("/", 1)[-1]
    return (
        "/__tests__/" in relpath
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _hit(line: str, next_line: str, wide: bool) -> bool:
    """True if a breadcrumb starts on ``line``, alone or wrapped onto the next."""
    patterns = (BREADCRUMB, NARRATION) if wide else (BREADCRUMB,)
    joined = line + " " + COMMENT_LEAD.sub("", next_line)
    for pattern in patterns:
        match = pattern.search(joined)
        # A match starting on the continuation line is reported there instead.
        if match and match.start() < len(line):
            return True
    return False


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
            wide = not _is_test_file(relpath)
            for lineno, line in enumerate(lines, start=1):
                next_line = lines[lineno] if lineno < len(lines) else ""
                hit = _hit(line, next_line, wide) or LINE_ANCHOR.search(line)
                if hit and (relpath, lineno) not in BASELINE:
                    offenders.append((relpath, lineno, line.strip()))

    if offenders:
        print(
            "Breadcrumbs or file:LINE anchors found (delete history the git log "
            "already has; cite a symbol, not a line):"
        )
        for relpath, lineno, line in offenders:
            print(f"  {relpath}:{lineno}: {line[:100]}")
        return 1
    print("Breadcrumbs: none found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
