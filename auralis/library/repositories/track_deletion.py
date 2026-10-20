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

from sqlalchemy import CursorResult, delete, update, select
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

    # Capture the playlists that are about to lose rows so their positions
    # can be re-compacted after the delete (#5573): the association rows are
    # removed without shifting, which left positions like (A,0),(C,2) and
    # made reorder_track's from_index lookups miss.
    affected_playlists = session.execute(
        select(track_playlist.c.playlist_id)
        .where(track_playlist.c.track_id.in_(track_ids))
        .distinct()
    ).scalars().all()

    for association in _TRACK_ASSOCIATIONS:
        session.execute(delete(association).where(association.c.track_id.in_(track_ids)))

    # Compact track_playlist positions for every affected playlist: renumber
    # the surviving rows 0..N-1 in their current order.
    for playlist_id in affected_playlists:
        surviving = session.execute(
            select(track_playlist.c.track_id)
            .where(track_playlist.c.playlist_id == playlist_id)
            .order_by(track_playlist.c.position)
        ).scalars().all()
        for new_position, survivor_id in enumerate(surviving):
            session.execute(
                update(track_playlist)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.track_id == survivor_id)
                .values(position=new_position)
            )
    # session.execute() is typed as Result although a DML statement returns a
    # CursorResult with rowcount.
    result = cast(CursorResult[Any], session.execute(delete(Track).where(Track.id.in_(track_ids))))
    return int(result.rowcount)
