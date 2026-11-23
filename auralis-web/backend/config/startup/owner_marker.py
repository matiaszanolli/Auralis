"""
The chunk-cache owner marker, read and written without trusting the shared temp root (#6514).

The marker sits directly in ``tempfile.gettempdir()``, which other local accounts can write on a
multi-user host. It was read with ``read_text()`` and written with ``write_text()``: a marker
another user pre-created naming a live PID suppressed this user's startup wipe (#4666/#4713), and a
symlink there made the write follow it. Now only a regular file owned by this user counts as a
marker, it is opened with ``O_NOFOLLOW``, and it is written 0600 after the same ownership check.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import stat
from pathlib import Path

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _ours(st: os.stat_result) -> bool:
    """A regular file owned by this user (no uid to compare on Windows, whose temp root is per user)."""
    return stat.S_ISREG(st.st_mode) and (not hasattr(os, "getuid") or st.st_uid == os.getuid())


def read_owned_marker(path: Path) -> str | None:
    """The marker's text if it is this user's regular file; None when absent, foreign, or a symlink."""
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as marker:
        if not _ours(os.fstat(marker.fileno())):
            return None
        return marker.read(64).decode(errors="replace").strip()  # corrupt bytes are not a PID (#6432)


def write_owned_marker(path: Path, text: str) -> None:
    """Write ``text`` to the marker 0600, never through a symlink and never into another user's file.

    Raises OSError when the entry is a symlink, not a regular file, or not owned by this user; the
    caller then simply does not record its claim (its own wipe decision ignores such a marker).
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | _NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as marker:
        if not _ours(os.fstat(marker.fileno())):
            raise PermissionError(f"{path.name} is not this user's file")
        marker.truncate(0)
        marker.write(text)
        if hasattr(os, "fchmod"):
            os.fchmod(marker.fileno(), 0o600)
