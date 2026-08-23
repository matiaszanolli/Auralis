"""
Artist Repository
~~~~~~~~~~~~~~~~

Data access layer for artist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, with_expression

from ..models import Album, Artist, Genre, Track, track_artist, track_genre
from .base import BaseRepository


def _track_count_subquery() -> Any:
    """Correlated COUNT of an artist's tracks (#5084).

    Same shape as the `order_by='track_count'` ordering expression in
    get_all(), and as AlbumRepository's _track_count_subquery (#4777). Artists
    with no tracks yield 0, not NULL, so no COALESCE is needed.
    """
    return (
        select(func.count())
        .select_from(track_artist)
        .where(track_artist.c.artist_id == Artist.id)
        .correlate(Artist)
        .scalar_subquery()
    )


def _album_count_subquery() -> Any:
    """Correlated COUNT of an artist's albums (#5084)."""
    return (
        select(func.count(Album.id))
        .where(Album.artist_id == Artist.id)
        .correlate(Artist)
        .scalar_subquery()
    )


def _attach_genre_names(session: Session, artists: Sequence[Artist]) -> None:
    """Populate `Artist.genre_names` for a page of artists in one query (#5084).

    The list endpoint needs the distinct genre names across each artist's
    tracks — and nothing else off those tracks. Eager-loading
    `Artist.tracks -> Track.genres` to get them hydrated every full Track row
    on the page, including the unbounded `lyrics` and `fingerprint_vector`
    Text columns, so cost scaled with tracks-per-artist rather than page size.

    This is one grouped SELECT over the association tables returning only
    (artist_id, genre name) pairs, so its row count is bounded by
    artists x distinct-genres, not by tracks.
    """
    artist_ids = [a.id for a in artists if a.id is not None]
    if not artist_ids:
        return

    rows = session.execute(
        select(track_artist.c.artist_id, Genre.name)
        .select_from(track_artist)
        .join(track_genre, track_genre.c.track_id == track_artist.c.track_id)
        .join(Genre, Genre.id == track_genre.c.genre_id)
        .where(track_artist.c.artist_id.in_(artist_ids))
        .distinct()
    ).all()

    by_artist: dict[int, set[str]] = {}
    for artist_id, genre_name in rows:
        if genre_name:
            by_artist.setdefault(artist_id, set()).add(genre_name)

    for artist in artists:
        # Sorted for a stable response order. `[]` means "no genres", which is
        # distinct from the None default meaning "this query did not ask".
        #
        # setattr() rather than a plain assignment: `Artist.genre_names` is
        # declared ClassVar so SQLAlchemy's annotation scanner leaves it
        # unmapped, and mypy rejects assigning to a ClassVar through an
        # instance even though shadowing it per-instance is ordinary Python.
        setattr(artist, 'genre_names', sorted(by_artist.get(artist.id, ())))


# Named eager-load constants (#5028), mirroring track_repository.py's
# _track_eager_options() / genre_repository.py's _GENRE_LOAD_OPTIONS /
# album_repository.py's _ALBUM_DETAIL_OPTIONS convention. #4236 fixed a
# DetachedInstanceError caused by exactly this duplication (one method's
# inline tuple fixed, its sibling's copy left stale) and its own proposed fix
# recommended this extraction — done here so a future read path can't
# silently omit it again.

# Single-artist detail reads: get_by_id/get_by_name hand the artist straight
# to to_dict(), which walks tracks->genres, tracks->album, and albums->tracks.
_ARTIST_DETAIL_OPTIONS = (
    selectinload(Artist.tracks).selectinload(Track.genres),
    selectinload(Artist.tracks).selectinload(Track.album),
    selectinload(Artist.albums).selectinload(Album.tracks),
)

# Paginated/listing reads (#4553): routers/artists.py walks
# artist.tracks -> track.genres and calls len() on artist.tracks/artist.albums
# — it never touches track.album or album.tracks, so those two chains are
# left out here (unlike _ARTIST_DETAIL_OPTIONS) to avoid pulling the full
# Track+Album row set for every artist on the page twice over (fixes #2516's
# N×M row explosion via selectinload instead of nested joinedload).
# #5084: the list endpoint reads only a genre-name set and two counts off each
# artist. Both now come from SQL — the counts from correlated subqueries via
# with_expression (Artist.track_count_expr/album_count_expr, mirroring Album's
# #4777 treatment), the genres from one grouped query in _attach_genre_names()
# — so no Track or Album row is hydrated at all. #4553 had already trimmed this
# to "what the serializer reads"; the residue was that even that scoped load
# was a full-Track hydration for a count-and-name-only consumer.
_ARTIST_LIST_OPTIONS = (
    with_expression(Artist.track_count_expr, _track_count_subquery()),
    with_expression(Artist.album_count_expr, _album_count_subquery()),
)


class ArtistRepository(BaseRepository):
    """Repository for artist database operations"""

    def get_by_id(self, artist_id: int) -> Artist | None:
        """Get artist by ID with relationships loaded"""
        with self._session_scope() as session:
            artist = (
                session.execute(
                    select(Artist)
                    .options(*_ARTIST_DETAIL_OPTIONS)
                    .where(Artist.id == artist_id)
                ).scalars().first()
            )
            if artist:
                session.expunge(artist)
            return artist

    def get_by_name(self, name: str) -> Artist | None:
        """Get artist by name with relationships loaded"""
        with self._session_scope() as session:
            artist = (
                session.execute(
                    select(Artist)
                    .options(*_ARTIST_DETAIL_OPTIONS)
                    .where(Artist.name == name)
                ).scalars().first()
            )
            if artist:
                session.expunge(artist)
            return artist

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'name') -> tuple[list[Artist], int]:
        """Get all artists with pagination and relationships loaded

        Args:
            limit: Maximum number of artists to return
            offset: Number of artists to skip
            order_by: Field to sort by ('name', 'album_count', 'track_count')

        Returns:
            Tuple of (artists list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(select(func.count()).select_from(Artist)).scalar_one()

            # Determine sort column
            if order_by == 'album_count':
                # Correlated subquery: no JOIN needed — evaluated per row by the DB engine.
                # Artists with no albums yield COUNT=0 (not NULL), so no COALESCE required.
                order_column = (
                    select(func.count(Album.id))
                    .where(Album.artist_id == Artist.id)
                    .correlate(Artist)
                    .scalar_subquery()
                    .desc()
                )
            elif order_by == 'track_count':
                order_column = (
                    select(func.count())
                    .select_from(track_artist)
                    .where(track_artist.c.artist_id == Artist.id)
                    .correlate(Artist)
                    .scalar_subquery()
                    .desc()
                )
            else:  # Default to name
                order_column = Artist.name.asc()

            # Eager-load exactly what the serializer reads, and nothing more
            # (#4553) — see _ARTIST_LIST_OPTIONS' docstring for what/why.
            artists = (
                session.execute(
                    select(Artist)
                    .options(*_ARTIST_LIST_OPTIONS)
                    .order_by(order_column)
                    .limit(limit)
                    .offset(offset)
                ).scalars().all()
            )

            _attach_genre_names(session, artists)

            for artist in artists:
                session.expunge(artist)
            return artists, total

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Artist], int]:
        """Search artists by name with pagination

        Args:
            query: Search string to match against artist name
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (artists list, total count of matching artists)
        """
        with self._session_scope() as session:
            # Escape LIKE metacharacters so a query containing '%' or '_' does
            # not accidentally match all rows (fixes #2405).
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_term = f"%{escaped}%"

            # Get total count of matching artists
            total = session.execute(
                select(func.count()).select_from(Artist)
                .where(Artist.name.ilike(search_term, escape='\\'))
            ).scalar_one()

            # Get paginated results. Same eager-load set as get_all() — see
            # _ARTIST_LIST_OPTIONS' docstring for what/why (#4553).
            artists = (
                session.execute(
                    select(Artist)
                    .options(*_ARTIST_LIST_OPTIONS)
                    .where(Artist.name.ilike(search_term, escape='\\'))
                    .order_by(Artist.name)
                    .limit(limit)
                    .offset(offset)
                ).scalars().all()
            )

            _attach_genre_names(session, artists)

            for artist in artists:
                session.expunge(artist)
            return artists, total

    def get_all_artists(self) -> list[Artist]:
        """Get all artists without pagination (for batch operations)

        Returns:
            List of all artists in the database with tracks and albums eagerly loaded.

        Note:
            Uses selectinload to avoid DetachedInstanceError when accessing .tracks
            or .albums on returned objects after the session is closed (fixes #2524).
        """
        with self._session_scope() as session:
            artists = (
                session.execute(
                    select(Artist)
                    # Deliberately distinct from both _ARTIST_DETAIL_OPTIONS and
                    # _ARTIST_LIST_OPTIONS (#5028 CONSISTENCY check): this batch
                    # export path skips Track.genres (neither constant's tracks
                    # chain is reusable here) and, unlike _ARTIST_LIST_OPTIONS,
                    # does need Artist.albums -> Album.tracks.
                    .options(
                        selectinload(Artist.tracks).selectinload(Track.album),
                        selectinload(Artist.tracks),
                        selectinload(Artist.albums).selectinload(Album.tracks),
                    )
                ).scalars().all()
            )
            for artist in artists:
                session.expunge(artist)
            return artists

    def update_artwork(
        self,
        artist_id: int,
        artwork_url: str,
        artwork_source: str,
        artwork_fetched_at: object | None = None
    ) -> bool:
        """Update artist artwork information

        Args:
            artist_id: ID of the artist to update
            artwork_url: URL of the artwork image
            artwork_source: Source of the artwork (e.g., 'MusicBrainz', 'Discogs', 'Last.fm')
            artwork_fetched_at: Timestamp when artwork was fetched (defaults to current UTC time)

        Returns:
            True if update successful, False if artist not found or update failed
        """
        from datetime import datetime, timezone

        with self._session_scope() as session:
            try:
                artist = session.execute(
                    select(Artist).where(Artist.id == artist_id)
                ).scalars().first()
                if not artist:
                    return False

                artist.artwork_url = artwork_url
                artist.artwork_source = artwork_source
                artist.artwork_fetched_at = artwork_fetched_at or datetime.now(timezone.utc)

                session.commit()
                return True
            except Exception:
                session.rollback()
                raise
