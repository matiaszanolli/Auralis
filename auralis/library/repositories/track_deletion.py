"""
Track deletion
~~~~~~~~~~~~~~

The one place that removes ``tracks`` rows, so the single-track and the two
bulk paths cannot drift apart again (#5557).

``track_artist``, ``track_genre`` and ``track_playlist`` reference ``tracks.id``
with no ``ON DELETE`` action and SQLite runs with ``PRAGMA foreign_keys=ON``.
A Core ``DELETE FROM tracks`` therefore fails with a FOREIGN KEY error as soon
as one doomed track has an artist, genre or playlist row, and unlike
``session.delete(track)`` it does not make the ORM clear those rows first.
``cleanup_missing_files()`` and ``remove_tracks_under_folder()`` hit exactly
that, and their callers swallow the exception, so the prunes of #5458/#5467
silently did nothing for nearly every real track. Fingerprint and
similarity-graph children are removed by the database's ``ondelete='CASCADE'``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.orm import Session

from ..models import Track, track_artist, track_genre, track_playlist

# The association tables that predate ON DELETE CASCADE.
_TRACK_ASSOCIATIONS = (track_playlist, track_genre, track_artist)


def delete_tracks_by_ids(session: Session, track_ids: Sequence[int]) -> int:
    """Delete tracks and their association rows in the caller's transaction.

    Does not commit; the caller owns the transaction. Callers batch their ids
    (the repository loops use 1000), well under SQLite's bound-variable limit.

    Returns:
        Number of ``tracks`` rows deleted.
    """
    if not track_ids:
        return 0
    for association in _TRACK_ASSOCIATIONS:
        session.execute(delete(association).where(association.c.track_id.in_(track_ids)))
    # session.execute() is typed as Result although a DML statement returns a
    # CursorResult with rowcount.
    result = cast(CursorResult[Any], session.execute(delete(Track).where(Track.id.in_(track_ids))))
    return int(result.rowcount)
