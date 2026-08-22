"""
Track Repository — Lookup Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Identity-lookup concerns for :class:`TrackRepository`, split out of
``track_repository.py`` (#4511): fetching one or many tracks by primary key
or by filepath, with the eager-loading every read path requires (#4500).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import select

from ..models import Track
from ..path_key import make_filepath_key
from .base import BaseRepository
from .track_repository import _iter_in_batches, _track_eager_options


class TrackRepositoryLookupMixin(BaseRepository):
    """Fetch tracks by id or filepath, singly or in bounded batches."""

    def get_by_id(self, track_id: int) -> Track | None:
        """Get track by ID with relationships loaded"""
        with self._session_scope() as session:
            track = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .where(Track.id == track_id)
            ).scalars().unique().first()
            if track:
                session.expunge(track)
            return track

    def get_by_ids(self, track_ids: list[int]) -> dict[int, Track]:
        """Get multiple tracks by ID using bounded ``WHERE IN`` queries.

        Returns a dict mapping track_id -> Track for found tracks.
        """
        if not track_ids:
            return {}
        unique_ids = list(dict.fromkeys(track_ids))
        with self._session_scope() as session:
            result: dict[int, Track] = {}
            for batch in _iter_in_batches(unique_ids):
                tracks = session.execute(
                    select(Track)
                    .options(*_track_eager_options())
                    .where(Track.id.in_(batch))
                ).scalars().unique().all()
                for track in tracks:
                    session.expunge(track)
                    result[track.id] = track
            return result

    def get_by_path(self, filepath: str) -> Track | None:
        """Get track by file path with relationships loaded"""
        with self._session_scope() as session:
            track = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .where(Track.filepath_key == make_filepath_key(filepath))
            ).scalars().unique().first()
            if track:
                session.expunge(track)
            return track

    def get_by_paths(self, filepaths: list[str]) -> dict[str, Track]:
        """Get tracks by filepath using bounded ``WHERE IN`` queries."""
        if not filepaths:
            return {}
        unique_paths = list(dict.fromkeys(filepaths))
        with self._session_scope() as session:
            result: dict[str, Track] = {}
            for batch in _iter_in_batches(unique_paths):
                tracks = session.execute(
                    select(Track)
                    .options(*_track_eager_options())
                    .where(Track.filepath_key.in_([make_filepath_key(p) for p in batch]))
                ).scalars().unique().all()
                for track in tracks:
                    session.expunge(track)
                    result[track.filepath] = track
            return result

    def get_id_by_filepath(self, filepath: str) -> int | None:
        """Return the track id for a filepath, or None if not present.

        Lightweight id-only lookup for callers that do not need the full
        Track object or its relationships (e.g. fingerprint cache joins).
        """
        with self._session_scope() as session:
            return session.execute(
                select(Track.id).where(Track.filepath_key == make_filepath_key(filepath))
            ).scalar_one_or_none()
