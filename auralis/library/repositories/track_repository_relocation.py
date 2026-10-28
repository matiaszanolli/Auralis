"""
Track Repository — Relocation Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Moved/renamed-file detection for the scanner (#5880). Rescan identity is the
path, so a reorganised library re-imported every moved file as a new row
while the post-scan prune deleted the old one, and with it the track's
playlist membership, favorite flag, play counts and fingerprint.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

from sqlalchemy import select

from ...utils.logging import info
from ..models import Track
from ..path_key import make_filepath_key
from .base import BaseRepository
from .track_repository_maintenance import _file_is_definitely_missing
from .track_repository_mutation import _reload_detached

# Same bytes give the same duration; the slack only absorbs analyzer changes
# between the scan that stored the row and this one.
RELOCATION_DURATION_TOLERANCE_SEC = 0.5


class TrackRepositoryRelocationMixin(BaseRepository):
    """Re-point a track whose file moved, instead of re-importing it."""

    def relocate_missing_track(
        self, filepath: str, filesize: int | None, duration: float | None
    ) -> Track | None:
        """Move the one missing-file track matching a newly found file to *filepath*.

        A move or rename keeps the bytes, so the identity is the exact byte
        size plus the duration. Only an unambiguous match is relocated:
        exactly one track with that signature whose own file is provably gone
        (ENOENT/ENOTDIR — an unreadable path is not, #5698). Unlike the prune,
        a gone parent directory still counts: renaming an album folder is the
        commonest reorganisation, and relocating keeps the row rather than
        deleting it. The row keeps its id and every association; the caller
        refreshes its metadata from the new file.

        Returns:
            The relocated track, or None when *filepath* is not a moved file
            (no or several candidates, or no size/duration to match on).
        """
        if not filesize or duration is None:
            return None
        with self._guarded("Failed to relocate moved track") as session:
            rows = session.execute(
                select(Track.id, Track.filepath).where(
                    Track.filesize == filesize,
                    Track.duration.between(
                        duration - RELOCATION_DURATION_TOLERANCE_SEC,
                        duration + RELOCATION_DURATION_TOLERANCE_SEC,
                    ),
                )
            ).all()
            moved = [row for row in rows if _file_is_definitely_missing(Path(row.filepath))]
            if len(moved) != 1:
                return None
            track = session.get(Track, moved[0].id)
            if track is None:
                return None
            track.filepath = filepath
            track.filepath_key = make_filepath_key(filepath)
            session.commit()
            info(f"Relocated moved file for track {moved[0].id}: {Path(filepath).name}")
            return _reload_detached(session, Track.id == moved[0].id)
        return None
