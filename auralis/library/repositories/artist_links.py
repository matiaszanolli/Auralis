"""
Artist Links
~~~~~~~~~~~~

Link a track to its artists in tag order (#6714).

track_artist is a plain ``secondary`` table, so the ORM writes only its two
foreign keys. link_artists() assigns the collection, flushes it, then stores
each artist's index in the file's tag as ``position``, which Track.artists is
ordered by. A reorder that keeps the same artists inserts no rows, so the
position update is what makes it stick.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from sqlalchemy import bindparam, update
from sqlalchemy.orm import Session

from ..models import Artist, Track, track_artist


def link_artists(session: Session, track: Track, artists: list[Artist]) -> None:
    """Set ``track.artists`` to *artists* and store their order.

    *track* must already be in *session*. Two tag spellings that normalize to
    one artist resolve to the same row; it is linked once, at its first place.
    """
    ordered = list(dict.fromkeys(artists))
    track.artists = ordered
    session.flush()
    if not ordered:
        return
    session.execute(
        update(track_artist)
        .where(track_artist.c.track_id == bindparam('tid'), track_artist.c.artist_id == bindparam('aid'))
        .values(position=bindparam('pos')),
        [{'tid': track.id, 'aid': artist.id, 'pos': index} for index, artist in enumerate(ordered)],
    )
