"""
Is a track's file really gone? (split out of track_repository_maintenance.py, #6273)

Decides, conservatively, which stored rows may be deleted as missing: an unreadable folder or an
unmounted volume is not evidence that the audio is gone.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...utils.logging import debug
from ..models import Track


def _under_removed_folder(track_path: Path, removed: Path, kept: Sequence[Path]) -> bool:
    """True when ``track_path`` is under ``removed`` and under no folder still configured."""
    return track_path.is_relative_to(removed) and not any(track_path.is_relative_to(k) for k in kept)


def _file_is_definitely_missing(path: Path) -> bool:
    """True only when ``path`` is provably gone (#5698).

    ``Path.exists()`` swallows every OSError, so an unreadable folder
    (EACCES — a permissions change, macOS TCC revocation, a sandbox), a
    dead mount (EIO/ESTALE) or any other I/O failure all read as "file
    deleted" — and ``cleanup_missing_files()`` then destroyed tracks along
    with their playlist rows, favourites and play counts. ``os.stat``
    separates the cases: only ENOENT/ENOTDIR prove the file is really
    gone; any other error means "cannot tell", which must skip, not
    delete.
    """
    try:
        os.stat(path)
        return False
    except (FileNotFoundError, NotADirectoryError):
        return True
    except OSError as e:
        debug(f"Cannot stat {path}: {e.strerror} ({e.errno}) — not treating as missing (#5698)")
        return False


def _track_file_is_missing(filepath: str | Path) -> bool:
    """The one missing-decision both cleanup passes share (#5698, #2525).

    A track whose parent directory is itself provably gone is treated as
    NOT missing — the volume is likely unmounted (NFS/SMB), and skipping
    beats deleting (#2525). Residual ambiguity, deliberately left: a
    track directly inside an empty *mount-point* directory on an
    unmounted volume stats as ENOENT and cannot be distinguished from a
    genuinely deleted file without scan-root readability context, which
    this repository layer does not have.
    """
    path = Path(filepath)
    if _file_is_definitely_missing(path.parent):
        debug(f"Parent directory gone (volume unmounted?), skipping: {path.parent}")
        return False
    return _file_is_definitely_missing(path)


def _confirmed_missing_ids(session: Session, rows: Sequence[Any]) -> list[int]:
    """Ids from *rows* (``id``/``filepath``) whose file is missing on two checks.

    One shared decision for both passes (#5698): stat errors that are not
    ENOENT/ENOTDIR (unreadable folder, dead mount) must skip, not delete; a gone
    parent means an unmounted volume (#2525). The second pass re-verifies the
    paths immediately before deletion to narrow the TOCTOU window (a file could
    reappear between the first check and the delete, #3310), batch-fetching the
    filepaths in a single IN query rather than one ``session.get()`` per id so
    re-verification stays O(batches), not O(missing tracks) (#4223).
    """
    missing_ids = [row.id for row in rows if _track_file_is_missing(str(row.filepath))]
    if not missing_ids:
        return []
    recheck_rows = session.execute(
        select(Track.id, Track.filepath).where(Track.id.in_(missing_ids))
    ).all()
    return [row.id for row in recheck_rows if _track_file_is_missing(str(row.filepath))]
