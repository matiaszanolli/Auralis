"""
Path identity for scan reservation (#6097).

``ScanCoordinator`` used to compare ``normpath(abspath())`` strings for exact
equality, so a nested directory (``/music`` vs ``/music/jazz``) or a symlinked
spelling of an active scan's root was treated as a different directory and
scanned concurrently with it -- both scanners missed ``get_by_path`` for the
same file, both ``add()``ed it, and the loser's IntegrityError was reported as
a failed insert for a file that had in fact been added.

Comparison is by real path and by ancestry; the paths a scan actually walks
keep the caller's own spelling (a symlinked library root must keep matching the
filepaths already stored under it).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os


def reservation_key(directory: str) -> str:
    """The identity a scan reserves for ``directory``: symlinks resolved."""
    return os.path.realpath(directory)


def _is_within(child: str, parent: str) -> bool:
    child, parent = os.path.normcase(child), os.path.normcase(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def paths_overlap(a: str, b: str) -> bool:
    """True when ``a`` and ``b`` are the same directory or one contains the other."""
    return _is_within(a, b) or _is_within(b, a)


def scan_roots(directories: list[str], recursive: bool) -> list[str]:
    """Drop roots a single request would otherwise walk twice.

    Exact duplicates (after symlink resolution) always collapse. With
    ``recursive`` a root inside another root is dropped too: the outer walk
    already visits every file under it. Without ``recursive`` a nested root is
    a different set of files and stays. The first spelling given wins, and
    input order is preserved.
    """
    keys = [reservation_key(d) for d in directories]
    kept: list[str] = []
    for i, directory in enumerate(directories):
        duplicate = any(keys[j] == keys[i] for j in range(i))
        nested = recursive and any(
            keys[j] != keys[i] and _is_within(keys[i], keys[j]) for j in range(len(keys))
        )
        if not (duplicate or nested):
            kept.append(directory)
    return kept
