"""
Orphan pruning
~~~~~~~~~~~~~~

Removes the albums, artists and genres that no track references any more.
Nothing did before, so every track delete (single, missing-file prune, scan
folder removal) left them behind: the Albums/Artists/Genres views listed
entries with no tracks and ``total_albums`` / ``total_artists`` overstated the
library (#5596). ``delete_tracks_by_ids`` calls this in the delete's own
transaction, so the two commit or roll back together.

A row is kept while anything points at it: an album while a track has it, an
artist while a track lists it or an album is owned by it, a genre while a track
has it. Albums go first so an artist whose last album was pruned goes with it.

An album's extracted artwork file is unlinked once the transaction commits, not
before: a rolled-back delete must not leave a surviving album pointing at a
file that is gone.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from sqlalchemy import delete, event, exists
from sqlalchemy.orm import Session

from ...utils.logging import debug
from ..artwork import ArtworkExtractor
from ..models import Album, Artist, Genre, Track, track_artist, track_genre

_PENDING_ARTWORK = "orphan_album_artwork"


def _unlink_pending_artwork(session: Session) -> None:
    for path in session.info.pop(_PENDING_ARTWORK, ()):
        ArtworkExtractor.delete_artwork(path)


def _forget_pending_artwork(session: Session) -> None:
    session.info.pop(_PENDING_ARTWORK, None)


def _unlink_artwork_after_commit(session: Session, paths: list[str]) -> None:
    """Queue *paths* for deletion when (and only if) *session* commits."""
    if _PENDING_ARTWORK not in session.info:
        event.listen(session, "after_commit", _unlink_pending_artwork)
        event.listen(session, "after_rollback", _forget_pending_artwork)
    session.info.setdefault(_PENDING_ARTWORK, []).extend(paths)


def prune_orphans(session: Session) -> dict[str, int]:
    """Delete childless albums, then artists, then genres in the caller's transaction.

    Does not commit. Returns the number of rows removed per table.
    """
    album_artwork = session.execute(
        delete(Album)
        .where(~exists().where(Track.album_id == Album.id))
        .returning(Album.artwork_path)
        .execution_options(synchronize_session=False)
    ).scalars().all()
    artists = session.execute(
        delete(Artist)
        .where(
            ~exists().where(track_artist.c.artist_id == Artist.id),
            ~exists().where(Album.artist_id == Artist.id),
        )
        .returning(Artist.id)
        .execution_options(synchronize_session=False)
    ).scalars().all()
    genres = session.execute(
        delete(Genre)
        .where(~exists().where(track_genre.c.genre_id == Genre.id))
        .returning(Genre.id)
        .execution_options(synchronize_session=False)
    ).scalars().all()

    artwork_paths = [path for path in album_artwork if path]
    if artwork_paths:
        _unlink_artwork_after_commit(session, artwork_paths)
    removed = {"albums": len(album_artwork), "artists": len(artists), "genres": len(genres)}
    if any(removed.values()):
        debug(f"Pruned orphans after track delete: {removed}")
    return removed
