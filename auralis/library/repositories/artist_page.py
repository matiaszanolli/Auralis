"""
Artist page reads (split from artist_repository.py, #5872): the detail header
and the track list, without hydrating the artist's Track rows.

``get_by_id`` eager-loads every Track (all columns, including the unbounded
``lyrics``/``comments`` Text and ``fingerprint_vector``) plus each album's
tracks again. The two artist-page endpoints read counts, album aggregates and
eight scalar track columns, so a compilation artist with tens of thousands of
tracks cost hundreds of MB per page open. #5084 fixed the list endpoint the
same way.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from sqlalchemy import collate, func, select
from sqlalchemy.orm import selectinload, with_expression

from ..models import Album, Artist, Track, track_artist
from .album_repository import _ALBUM_LIST_OPTIONS
from .base import BaseRepository, correlated_count

# The artist's track count, and per album what serialize_album() reads: the
# artist (one row) and the SQL aggregates, never Album.tracks.
_ARTIST_PAGE_OPTIONS = (
    with_expression(Artist.track_count_expr, correlated_count(track_artist, track_artist.c.artist_id, Artist)),
    selectinload(Artist.albums).options(*_ALBUM_LIST_OPTIONS),
)


class ArtistPageMixin(BaseRepository):
    """Artist-page methods of ArtistRepository."""

    def get_page(self, artist_id: int) -> Artist | None:
        """The artist with ``track_count_expr`` set and its albums carrying
        ``track_count_expr``/``total_duration_expr``; no Track row is loaded."""
        with self._session_scope() as session:
            return self._first_detached(
                session,
                select(Artist).options(*_ARTIST_PAGE_OPTIONS).where(Artist.id == artist_id),
            )

    def get_track_rows(self, artist_id: int) -> tuple[str, list[dict[str, Any]]] | None:
        """``(artist name, track rows)``, or None when the artist does not exist.

        Each row holds only what ``TrackInArtist`` ships, sorted in SQL by album
        title (album-less tracks first, case-insensitive like the browse lists,
        #5869), disc, track number and id.
        """
        with self._session_scope() as session:
            name = session.execute(
                select(Artist.name).where(Artist.id == artist_id)
            ).scalar_one_or_none()
            if name is None:
                return None
            album_title = func.coalesce(Album.title, '')
            rows = session.execute(
                select(
                    Track.id, Track.title, Album.title.label('album'), Album.id.label('album_id'),
                    Track.duration, Track.track_number, Track.disc_number, Track.format,
                )
                .join(track_artist, track_artist.c.track_id == Track.id)
                .outerjoin(Album, Album.id == Track.album_id)
                .where(track_artist.c.artist_id == artist_id)
                .order_by(
                    collate(album_title, 'NOCASE'),
                    func.coalesce(Track.disc_number, 1),
                    func.coalesce(Track.track_number, 999),
                    Track.id,
                )
            ).mappings().all()
            return name, [dict(row) for row in rows]
