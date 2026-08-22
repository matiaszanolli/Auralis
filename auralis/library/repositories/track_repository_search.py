"""
Track Repository — Search Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Search/browse concerns for :class:`TrackRepository`, split out of
``track_repository.py`` (#4511): free-text search, genre/artist filtering,
recent/popular/favorites/all listings, and simple similarity lookups.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import func, or_, select

from ..models import Album, Artist, Genre, Track
from .base import BaseRepository
from .track_repository import _VALID_TRACK_ORDER_COLUMNS, _track_eager_options


class TrackRepositorySearchMixin(BaseRepository):
    """Search, filter, and browse tracks."""

    def search(self, query: str, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Track], int]:
        """
        Search tracks by title, artist, album, or genre

        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Number of results to skip (for pagination)
            order_by: Column name to order by ('title', 'created_at', 'play_count', etc.)

        Returns:
            Tuple of (matching tracks, total count)
        """
        with self._session_scope() as session:
            # Escape LIKE metacharacters so a query containing '%' or '_' does
            # not accidentally match all rows (fixes #2405).
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_term = f"%{escaped}%"

            # Build shared filter for count and results statements
            search_filter = or_(
                Track.title.ilike(search_term, escape='\\'),
                Artist.name.ilike(search_term, escape='\\'),
                Album.title.ilike(search_term, escape='\\')
            )

            # Get total count
            total = session.execute(
                select(func.count(func.distinct(Track.id)))
                .join(Track.artists, isouter=True)
                .join(Track.album, isouter=True)
                .where(search_filter)
            ).scalar_one()

            # Whitelist to prevent arbitrary attribute access
            if order_by not in _VALID_TRACK_ORDER_COLUMNS:
                order_by = 'title'
            order_column = getattr(Track, order_by, Track.title)

            # Get paginated results. LIMIT/OFFSET has implementation-defined row
            # order without ORDER BY — especially with .distinct() after an
            # outer join — so two calls with the same query/offset can return
            # duplicate or skipped rows across pages (fixes #4796). Track.id is
            # a stable tiebreaker since order_column alone may not be unique.
            results = session.execute(
                select(Track)
                .join(Track.artists, isouter=True)
                .join(Track.album, isouter=True)
                .options(*_track_eager_options(collections_via_selectin=True))
                .where(search_filter)
                .distinct()
                .order_by(order_column.asc(), Track.id.asc())
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            for track in results:
                session.expunge(track)
            return results, total

    def get_by_genre(self, genre_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by genre"""
        with self._session_scope() as session:
            tracks = session.execute(
                select(Track)
                .join(Track.genres)
                .options(*_track_eager_options(collections_via_selectin=True))
                .where(Genre.name == genre_name)
                .limit(limit)
            ).scalars().all()
            for track in tracks:
                session.expunge(track)
            return tracks

    def get_by_artist(self, artist_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by artist"""
        with self._session_scope() as session:
            # Use eager loading to load relationships before session closes
            tracks = session.execute(
                select(Track).join(Track.artists).where(
                    Artist.name == artist_name
                ).options(
                    *_track_eager_options()  # includes selectinload(genres) — #2523/#4500
                ).limit(limit)
            ).scalars().unique().all()

            # Expunge from session to make objects persistent across session close
            for track in tracks:
                session.expunge(track)

            return tracks

    def get_recent(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get recently added tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Track)
            ).scalar_one()

            # Get paginated results
            results = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .order_by(Track.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            for track in results:
                session.expunge(track)
            return results, total

    def get_popular(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get most played tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Track)
            ).scalar_one()

            # Get paginated results
            results = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .order_by(Track.play_count.desc())
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            for track in results:
                session.expunge(track)
            return results, total

    def get_favorites(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get favorite tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Track)
                .where(Track.favorite == True)
            ).scalar_one()

            # Get paginated results
            results = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .where(Track.favorite == True)
                .order_by(Track.title.asc())
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            for track in results:
                session.expunge(track)
            return results, total

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Track], int]:
        """Get all tracks with pagination and total count

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)
            order_by: Column name to order by ('title', 'created_at', 'play_count', etc.)

        Returns:
            Tuple of (list of Track objects, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Track)
            ).scalar_one()

            # Get tracks for current page (whitelist to prevent arbitrary attribute access)
            if order_by not in _VALID_TRACK_ORDER_COLUMNS:
                order_by = 'title'
            order_column = getattr(Track, order_by, Track.title)
            tracks = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .order_by(order_column.asc())
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            for track in tracks:
                session.expunge(track)
            return tracks, total

    def find_similar(self, track: Track, limit: int = 5) -> list[Track]:
        """
        Find similar tracks based on audio characteristics

        Args:
            track: Reference track
            limit: Maximum number of results

        Returns:
            List of similar tracks
        """
        with self._session_scope() as session:
            # Simple similarity based on genre and artist
            # In production, would use more sophisticated audio fingerprinting
            similar_tracks: list[Track] = []
            seen_ids: set[int] = set()

            # Batch query: find tracks by any of the same artists (#2072)
            if track.artists:
                artist_tracks = session.execute(
                    select(Track)
                    .options(*_track_eager_options(collections_via_selectin=True))
                    .where(Track.artists.any(Artist.id.in_([a.id for a in track.artists])))
                    .where(Track.id != track.id)
                    .limit(limit)
                ).scalars().all()
                for t in artist_tracks:
                    if t.id not in seen_ids:
                        similar_tracks.append(t)
                        seen_ids.add(t.id)

            # Batch query: find tracks in any of the same genres (#2072)
            if track.genres and len(similar_tracks) < limit:
                genre_filters = [
                    Track.genres.any(Genre.id.in_([g.id for g in track.genres])),
                    Track.id != track.id,
                ]
                if seen_ids:
                    genre_filters.append(~Track.id.in_(seen_ids))
                genre_tracks = session.execute(
                    select(Track)
                    .options(*_track_eager_options(collections_via_selectin=True))
                    .where(*genre_filters)
                    .limit(limit - len(similar_tracks))
                ).scalars().all()
                for t in genre_tracks:
                    if t.id not in seen_ids:
                        similar_tracks.append(t)
                        seen_ids.add(t.id)

            result = similar_tracks[:limit]
            for t in set(result):
                session.expunge(t)
            return result
