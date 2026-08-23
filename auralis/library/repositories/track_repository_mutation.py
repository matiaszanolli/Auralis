"""
Track Repository — Mutation Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Field-update concerns for :class:`TrackRepository`, split out of
``track_repository.py`` (#4511): updating an existing track's fields
(by filepath or by id) and the gated metadata-only update path (#4555).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...utils.logging import debug, error, info, warning
from ..models import Album, Artist, Genre, Track
from ..path_key import make_filepath_key
from .base import BaseRepository
from .track_repository import _filter_metadata_fields, _track_eager_options


class TrackRepositoryMutationMixin(BaseRepository):
    """Update an existing track's fields, relationships, or metadata."""

    # Provided by TrackRepositoryLifecycleMixin — bare annotations so type
    # checkers know this mixin depends on them without shadowing the real
    # implementations via MRO.
    _get_or_create_artists: Callable[[Session, list[str]], list[Artist]]
    _get_or_create_genres: Callable[[Session, list[str]], list[Genre]]

    def _update_artists(self, session: Session, track: Track, artist_names: list[str]) -> None:
        """Update track artists using normalized name matching"""
        track.artists = self._get_or_create_artists(session, artist_names)

    def _update_genres(self, session: Session, track: Track, genre_names: list[str]) -> None:
        """Update track genres"""
        track.genres = self._get_or_create_genres(session, genre_names)

    def update_by_filepath(self, filepath: str, track_info: dict[str, Any]) -> Track | None:
        """
        Update track by filepath

        Args:
            filepath: Path to track file
            track_info: Dictionary with updated track information

        Returns:
            Updated Track object if successful, None if failed
        """
        with self._session_scope() as session:
            try:
                track = session.execute(
                    select(Track).where(Track.filepath_key == make_filepath_key(filepath))
                ).scalars().first()
                if not track:
                    warning(f"Track not found: {filepath}")
                    return None

                # Update basic fields
                for key in ['title', 'duration', 'sample_rate', 'bit_depth', 'channels',
                           'format', 'filesize', 'peak_level', 'rms_level', 'dr_rating',
                           'lufs_level', 'track_number', 'disc_number', 'year', 'comments']:
                    if key in track_info:
                        setattr(track, key, track_info[key])

                # Update artists
                if 'artists' in track_info:
                    self._update_artists(session, track, track_info['artists'])

                # Update genres
                if 'genres' in track_info:
                    self._update_genres(session, track, track_info['genres'])

                # Update album
                if 'album' in track_info:
                    album = session.execute(select(Album).where(Album.title == track_info['album'])).scalars().first()
                    if not album:
                        album = Album(title=track_info['album'], year=track_info.get('year'))
                        session.add(album)
                    track.album = album

                session.commit()
                # Re-query with eager loading before detaching from session
                track = session.execute(
                    select(Track)
                    .options(*_track_eager_options())
                    .where(Track.filepath_key == make_filepath_key(filepath))
                ).scalars().unique().first()
                info(f"Updated track: {track.title}")
                session.expunge(track)
                return track

            except Exception as e:
                session.rollback()
                error(f"Failed to update track: {e}")
                return None

    def update(self, track_id: int, track_info: dict[str, Any]) -> Track | None:
        """
        Update a track by ID

        Args:
            track_id: Track ID to update
            track_info: Dictionary with updated track information

        Returns:
            Updated track or None if not found
        """
        with self._session_scope() as session:
            try:
                track = session.execute(select(Track).where(Track.id == track_id)).scalars().first()
                if not track:
                    return None

                # Update simple fields
                for field in ['title', 'duration', 'bitrate', 'sample_rate', 'year', 'track_number', 'disc_number']:
                    if field in track_info:
                        setattr(track, field, track_info[field])

                # Update artists if provided
                if 'artist' in track_info or 'artists' in track_info:
                    artists = track_info.get('artists', [track_info.get('artist')] if track_info.get('artist') else [])
                    if artists:
                        self._update_artists(session, track, artists)

                # Update genres if provided
                if 'genre' in track_info or 'genres' in track_info:
                    genres = track_info.get('genres', [track_info.get('genre')] if track_info.get('genre') else [])
                    if genres:
                        self._update_genres(session, track, genres)

                # Update album if provided
                if 'album' in track_info:
                    album_title = track_info['album']
                    if album_title:
                        album = session.execute(select(Album).where(Album.title == album_title)).scalars().first()
                        if not album:
                            album = Album(title=album_title)
                            session.add(album)
                        track.album = album

                session.commit()
                # Re-query with eager loading before detaching from session
                track = session.execute(
                    select(Track)
                    .options(*_track_eager_options())
                    .where(Track.id == track_id)
                ).scalars().unique().first()
                debug(f"Updated track: {track.title}")
                session.expunge(track)
                return track
            except Exception as e:
                session.rollback()
                error(f"Failed to update track: {e}")
                return None

    def update_metadata(self, track_id: int, **fields: Any) -> Track | None:
        """
        Update track metadata fields.

        Args:
            track_id: Track ID
            **fields: Fields to update (only non-None values used)

        Returns:
            Updated track or None if not found

        Raises:
            Exception: If update fails
        """
        with self._session_scope() as session:
            try:
                track = session.execute(select(Track).where(Track.id == track_id)).scalars().first()
                if not track:
                    return None

                # Update only provided fields, and only ones that are actually
                # editable metadata — never structural columns (#4555).
                for key, value in _filter_metadata_fields(track_id, fields).items():
                    if hasattr(track, key) and value is not None:
                        setattr(track, key, value)

                session.commit()
                session.refresh(track)
                session.expunge(track)
                debug(f"Updated track metadata: {track.title}")
                return track
            except Exception as e:
                session.rollback()
                error(f"Failed to update track metadata {track_id}: {e}")
                raise

    def update_metadata_batch(
        self, updates: list[tuple[int, dict[str, Any]]]
    ) -> list[int]:
        """Update metadata fields for multiple tracks in one transaction.

        Opens a single session, applies all field mutations, and commits once,
        avoiding the N×session-open/commit overhead of per-track calls to
        ``update_metadata`` (fixes #3857 / BE-PF-8).

        Args:
            updates: List of ``(track_id, fields_dict)`` pairs.  Fields that
                are ``None`` are silently skipped (same semantics as
                ``update_metadata``).

        Returns:
            List of track IDs that were successfully updated (tracks not found
            in the DB are omitted).
        """
        if not updates:
            return []

        with self._session_scope() as session:
            try:
                successful: list[int] = []
                for track_id, fields in updates:
                    track = session.execute(
                        select(Track).where(Track.id == track_id)
                    ).scalars().first()
                    if not track:
                        continue
                    # Same allowlist as update_metadata — structural columns are
                    # not writable through a metadata path (#4555).
                    for key, value in _filter_metadata_fields(track_id, fields).items():
                        if hasattr(track, key) and value is not None:
                            setattr(track, key, value)
                    successful.append(track_id)

                session.commit()
                debug(f"Batch-updated metadata for {len(successful)} track(s)")
                return successful
            except Exception as e:
                session.rollback()
                error(f"Failed to batch-update track metadata: {e}")
                raise
