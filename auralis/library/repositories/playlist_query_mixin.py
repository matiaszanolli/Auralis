"""
Playlist Query Mixin
~~~~~~~~~~~~~~~~~~~~

Paginated listing and search for ``PlaylistRepository``, extracted from
``playlist_repository.py`` (#4511) to stay under the project's 300-line
convention. Pairs with ``playlist_crud_mixin.py`` (single-playlist CRUD)
and ``playlist_membership_mixin.py`` / ``playlist_ordering_mixin.py``
(track membership and position management) — all four are always mixed
into ``PlaylistRepository`` together.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import with_expression
from sqlalchemy.sql.selectable import ScalarSelect

from ..models import Playlist, Track
from ..models.base import track_playlist
from .base import BaseRepository, escape_like


class PlaylistQueryMixin(BaseRepository):
    """Multi-playlist listing/search, sharing the repository's session factory.

    Inherits ``BaseRepository`` directly for ``get_session``/
    ``_session_scope`` (#4604) — see ``playlist_membership_mixin.py`` for
    why a bare annotation doesn't work for ``_session_scope`` here.
    """

    def get_all(self, limit: int = 50, offset: int = 0) -> tuple[list[Playlist], int]:
        """Get a page of playlists, with each playlist's track count.

        Args:
            limit: Maximum number of playlists to return
            offset: Number of playlists to skip

        Returns:
            Tuple of (playlists list, total count of playlists)

        Note:
            #4554: this used to take no arguments and unconditionally
            ``selectinload`` every playlist's full ``tracks`` collection, so
            "list playlists" was an unbounded read of the entire
            playlist-to-track association table whose cost scaled in both
            playlist count *and* tracks-per-playlist. It is now paginated like
            the peer album/artist/track endpoints, and the per-playlist track
            count comes from a correlated ``COUNT`` over the association table
            instead of loading full Track rows just to call ``len()`` on them.
        """
        with self._session_scope() as session:
            total = session.execute(
                select(func.count()).select_from(Playlist)
            ).scalar_one()

            # Correlated subqueries, shared with search() so both paths
            # attach identical per-row aggregates. Mirrors the pattern already
            # used in ArtistRepository.get_all().
            track_count = self._track_count_subquery()
            total_duration = self._total_duration_subquery()

            playlists = session.execute(
                select(Playlist)
                .options(
                    with_expression(Playlist.track_count_expr, track_count),
                    with_expression(Playlist.total_duration_expr, total_duration),
                )
                .order_by(Playlist.name)
                .limit(limit)
                .offset(offset)
            ).scalars().all()

            # #3709: expunge_all() detaches the playlists AND any nested Track
            # objects from the session. The previous per-playlist
            # `session.expunge(playlist)` only detached the parent; nested
            # tracks remained tied to the about-to-close session, so any
            # downstream access to `track.artists` / `track.album` (not
            # pre-loaded here) raised DetachedInstanceError.
            session.expunge_all()
            return list(playlists), total

    def _track_count_subquery(self) -> ScalarSelect[int]:
        """Correlated COUNT of a playlist's tracks, evaluated per row.

        No JOIN and no row multiplication; playlists with no tracks yield 0
        (not NULL), so no COALESCE is needed.
        """
        return (
            select(func.count())
            .select_from(track_playlist)
            .where(track_playlist.c.playlist_id == Playlist.id)
            .correlate(Playlist)
            .scalar_subquery()
        )

    def _total_duration_subquery(self) -> ScalarSelect[float]:
        """Correlated SUM of a playlist's track durations.

        COALESCE because SUM over zero rows is NULL, unlike COUNT.
        """
        return (
            select(func.coalesce(func.sum(Track.duration), 0.0))
            .select_from(track_playlist)
            .join(Track, Track.id == track_playlist.c.track_id)
            .where(track_playlist.c.playlist_id == Playlist.id)
            .correlate(Playlist)
            .scalar_subquery()
        )

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Playlist], int]:
        """Search playlists by name or description.

        Playlist search was never implemented — not here, and not on the
        deprecated library facade that preceded this repository — so
        ``db.playlists.search(...)`` had always been an ``AttributeError``
        (#5171).

        Returns ``(results, total)`` like every peer repository's ``search()``
        so callers can paginate correctly; ``total`` is the full match count,
        not the length of this page.

        Args:
            query: Search string, matched case-insensitively as a substring
                against ``name`` and ``description``.
            limit: Maximum number of playlists to return.
            offset: Number of playlists to skip.

        Returns:
            Tuple of (matching playlists, total match count).
        """
        with self._session_scope() as session:
            search_term = f"%{escape_like(query)}%"
            search_filter = or_(
                Playlist.name.ilike(search_term, escape='\\'),
                Playlist.description.ilike(search_term, escape='\\'),
            )

            total = session.execute(
                select(func.count()).select_from(Playlist).where(search_filter)
            ).scalar_one()

            # Same per-row aggregates get_all() attaches, so a searched
            # playlist serialises identically to a listed one — otherwise
            # to_dict() reports track_count 0 for search hits (#4554).
            playlists = session.execute(
                select(Playlist)
                .options(
                    with_expression(Playlist.track_count_expr, self._track_count_subquery()),
                    with_expression(Playlist.total_duration_expr, self._total_duration_subquery()),
                )
                .where(search_filter)
                # Playlist.name is not unique, so id is the stable tiebreaker
                # that keeps LIMIT/OFFSET pages from overlapping (cf. #4796).
                .order_by(Playlist.name, Playlist.id)
                .limit(limit)
                .offset(offset)
            ).scalars().all()

            # expunge_all(), not per-playlist expunge: detaches nested Track
            # rows too, so downstream access does not raise
            # DetachedInstanceError (#3709).
            session.expunge_all()
            return list(playlists), total
