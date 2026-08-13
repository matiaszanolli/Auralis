"""
Filepath Matching Keys
~~~~~~~~~~~~~~~~~~~~~~

``Track.filepath`` stores the path exactly as discovered, because that is the
string used to open the file — case-folding it would break I/O on
case-sensitive filesystems. But Windows (NTFS) and macOS (default APFS) are
case-insensitive-but-preserving, so the *same physical file* is reachable via
several differently-cased strings the OS treats as identical and a plain
``filepath == ?`` comparison treats as different. Rescanning with any case
variance then inserts a duplicate row, and ``unique=True`` on ``filepath``
does not stop it: the constraint only rejects an *identical* string (#4842).

So matching goes through a second, derived value — ``Track.filepath_key`` —
which is what lookups compare and what carries the unique index.

**Why not ``os.path.normcase``**, which is the obvious answer and what #4842
proposes: it is a no-op on macOS. ``os.path`` resolves to ``posixpath`` on
Darwin just as it does on Linux, and ``posixpath.normcase`` returns the string
unchanged. Relying on it would have fixed Windows and left macOS — half the
reported blast radius — silently broken. The case-folding here is therefore
explicit rather than delegated to the stdlib.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import os
import sys

__all__ = ["filesystem_is_case_insensitive", "make_filepath_key"]

# Windows (NTFS) and macOS (APFS/HFS+) default to case-insensitive. Linux
# (ext4/btrfs/xfs) is case-sensitive.
#
# This is a platform default, not a per-volume probe: a case-sensitive APFS
# volume or a case-insensitive mount on Linux would be misjudged. A probe is
# possible but has to run per directory and per scan, and the failure mode of
# guessing wrong is asymmetric — see the note in `make_filepath_key`.
_CASE_INSENSITIVE_PLATFORMS = frozenset({"win32", "cygwin", "darwin"})


def filesystem_is_case_insensitive() -> bool:
    """Whether this platform's filesystem treats paths case-insensitively."""
    return sys.platform in _CASE_INSENSITIVE_PLATFORMS


def make_filepath_key(filepath: str | os.PathLike[str]) -> str:
    """Derive the matching key for a discovered path.

    On a case-insensitive platform the key is case-folded, so
    ``/Music/Song.mp3`` and ``/music/song.MP3`` collapse to one key and the
    second scan recognises the file instead of inserting a duplicate.

    On a case-sensitive platform the key preserves case, because there those
    two paths genuinely *are* different files. Folding everywhere would be the
    worse error: it would make a rescan silently skip a real, distinct track,
    which is data loss rather than duplication. Duplication is recoverable;
    a track that never got added is not obviously wrong to the user.

    Separators are normalised in both cases so a path that differs only in
    ``/`` vs ``\\`` does not fork either.

    Args:
        filepath: Path as discovered by the scanner.

    Returns:
        The value to store in and compare against ``Track.filepath_key``.
    """
    normalised = os.path.normpath(str(filepath))
    if filesystem_is_case_insensitive():
        # str.casefold(), not str.lower(): lower() leaves several non-ASCII
        # pairs uncollapsed, and music libraries are full of non-ASCII titles.
        return normalised.replace("\\", "/").casefold()
    return normalised.replace("\\", "/")
