"""
Track Repository — Lifecycle Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create/delete concerns for :class:`TrackRepository`, split out of
``track_repository.py`` (#4511): validating/normalizing incoming track info,
resolving-or-creating the artist/genre/album rows a new track references, and
adding or deleting a track row itself.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, TypeVar

from sqlalchemy import and_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from ...utils.logging import debug, error, info, warning
from ..models import (
    Album,
    Artist,
    Genre,
    Track,
)
from ..path_key import make_filepath_key
from ..utils.artist_normalizer import normalize_artist_name
from .base import BaseRepository
from .track_deletion import delete_tracks_by_ids
from .track_repository import _track_eager_options


_M = TypeVar("_M", Artist, Genre, Album)


def _get_or_create(
    session: Session, model: type[_M], where: Any, required: bool = True, **values: Any
) -> _M:
    """Select the row matching ``where``, inserting ``values`` first if it is missing.

    The insert is ``INSERT ... ON CONFLICT DO NOTHING`` followed by a re-select,
    not a SAVEPOINT: pysqlite's legacy transaction mode lets a SAVEPOINT open
    the SQLite transaction itself, so its outermost RELEASE *commits* — the new
    artist/genre/album then survived a rollback of the surrounding session and
    a failed ``add()`` left orphans (#5717). A plain INSERT begins the
    session's own transaction, so rollback takes it back. A concurrent loser's
    conflicting INSERT is ignored and the re-select finds the winner's row
    (#2594). ``required`` re-raises ``NoResultFound`` if no row exists even
    after the insert.
    """
    row = session.execute(select(model).where(where)).scalars().first()
    if row is None:
        session.execute(sqlite_insert(model).values(**values).on_conflict_do_nothing())
        found = session.execute(select(model).where(where)).scalars()
        row = found.one() if required else found.first()
    return row  # type: ignore[return-value]


class TrackRepositoryLifecycleMixin(BaseRepository):
    """Track creation and deletion, plus the artist/genre/album resolution
    helpers ``add()`` depends on.
    """

    # Set by TrackRepository.__init__; annotated here for type-checking.
    album_repository: Any | None

    def _validate_and_normalize_track_info(self, track_info: dict[str, Any]) -> None:
        """Validate required fields/ranges and normalize text fields in place (#2073)."""
        if 'duration' in track_info and (not isinstance(track_info['duration'], (int, float)) or track_info['duration'] < 0):
            track_info['duration'] = 0.0
        if 'sample_rate' in track_info and (not isinstance(track_info['sample_rate'], (int, float)) or track_info['sample_rate'] <= 0):
            track_info.pop('sample_rate', None)
        if 'channels' in track_info and track_info['channels'] not in (1, 2, 4, 6, 8):
            track_info.pop('channels', None)
        # Truncate excessively long text fields
        for field, max_len in (('title', 500), ('album', 500)):
            if field in track_info and isinstance(track_info[field], str) and len(track_info[field]) > max_len:
                track_info[field] = track_info[field][:max_len]
        if 'artists' in track_info:
            track_info['artists'] = [a[:200] for a in track_info['artists'] if isinstance(a, str)]

    def _get_or_create_artists(self, session: Session, artist_names: list[str]) -> list[Artist]:
        """Resolve or create artists by normalized name matching.

        Handles concurrent scans where two sessions try to insert the same
        artist simultaneously — the loser's INSERT is ignored and we fall back
        to querying (fixes #2594).
        """
        artists = []
        for name in artist_names:
            normalized = normalize_artist_name(name)
            try:
                artist = _get_or_create(
                    session, Artist, Artist.normalized_name == normalized,
                    name=name, normalized_name=normalized,
                )
            except NoResultFound:
                # `name` is taken by a row stored under an older normalisation
                # (symbol-only names such as "!!!" were keyed ''); adopt it and
                # re-key it so the next lookup matches (#5720).
                artist = session.execute(select(Artist).where(Artist.name == name)).scalars().one()
                artist.normalized_name = normalized
            artists.append(artist)
        return artists

    def _get_or_create_genres(self, session: Session, genre_names: list[str]) -> list[Genre]:
        """Resolve or create genres by name (same concurrent-insert handling as artists, fixes #2594)."""
        return [_get_or_create(session, Genre, Genre.name == name, name=name) for name in genre_names]

    def _get_or_create_album(
        self, session: Session, album_title: str, year: Any, artist_id: int | None
    ) -> Album | None:
        """Resolve or create an album for the given artist (same concurrent-insert handling as artists, fixes #3365)."""
        album_filter = Album.title == album_title
        if artist_id is not None:
            album_filter = and_(album_filter, Album.artist_id == artist_id)
        if artist_id is None:
            return session.execute(select(Album).where(album_filter)).scalars().first()
        try:
            return _get_or_create(
                session, Album, album_filter, required=False,
                title=album_title, artist_id=artist_id, year=year,
            )
        except IntegrityError:  # e.g. the artist row vanished (FK); no album
            return session.execute(select(Album).where(album_filter)).scalars().first()

    def add(self, track_info: dict[str, Any]) -> Track | None:
        """
        Add a track to the library

        Args:
            track_info: Dictionary with track information

        Returns:
            Track object if successful, None if failed
        """
        if not track_info.get('filepath'):
            warning("Cannot add track: missing 'filepath'")
            return None
        self._validate_and_normalize_track_info(track_info)

        with self._guarded("Failed to add track") as session:
            # Check if track already exists
            existing = session.execute(
                select(Track).options(
                    *_track_eager_options()
                ).where(Track.filepath_key == make_filepath_key(track_info['filepath']))
            ).scalars().unique().first()
            if existing:
                session.expunge(existing)
                warning(f"Track already exists: {track_info['filepath']}")
                return existing

            # Auto-extract basic audio info if not provided
            if 'format' not in track_info or 'sample_rate' not in track_info or 'channels' not in track_info:
                try:
                    import soundfile as sf
                    sf_info = sf.info(track_info['filepath'])
                    if 'format' not in track_info:
                        track_info['format'] = sf_info.format
                    if 'sample_rate' not in track_info:
                        track_info['sample_rate'] = sf_info.samplerate
                    if 'channels' not in track_info:
                        track_info['channels'] = sf_info.channels
                    if 'duration' not in track_info:
                        track_info['duration'] = sf_info.duration
                except Exception as e:
                    debug(f"Failed to auto-extract audio info: {e}")

            artists = self._get_or_create_artists(session, track_info.get('artists', []))
            album = None
            if track_info.get('album'):
                album = self._get_or_create_album(
                    session, track_info['album'], track_info.get('year'),
                    artists[0].id if artists else None
                )
            genres = self._get_or_create_genres(session, track_info.get('genres', []))

            # Create track
            track = Track(
                title=track_info.get('title', 'Unknown'),
                filepath=track_info['filepath'],
                filepath_key=make_filepath_key(track_info['filepath']),
                duration=track_info.get('duration'),
                sample_rate=track_info.get('sample_rate'),
                channels=track_info.get('channels'),
                format=track_info.get('format'),
                filesize=track_info.get('filesize'),
                file_mtime=track_info.get('file_mtime'),
                dr_rating=track_info.get('dr_rating'),
                album=album,
                track_number=track_info.get('track_number'),
                disc_number=track_info.get('disc_number'),
                year=track_info.get('year'),
                comments=track_info.get('comments'),
            )

            # Add relationships
            track.artists = artists
            track.genres = genres

            session.add(track)
            session.commit()
            session.refresh(track)
            session.refresh(album) if album else None

            info(f"Added track: {track.title}")

            # Extract artwork if album doesn't have artwork yet and album_repository is available
            if album and self.album_repository and not album.artwork_path:
                try:
                    debug(f"Extracting artwork for album: {album.title}")
                    artwork_path = self.album_repository.artwork_extractor.extract_artwork(
                        track_info['filepath'], album.id
                    )
                    if artwork_path:
                        album.artwork_path = artwork_path
                        session.commit()
                        info(f"Extracted artwork for album: {album.title}")
                except Exception as artwork_error:
                    warning(f"Failed to extract artwork for album {album.title}: {artwork_error}")

            # Re-query with eager loading before detaching from session
            reloaded = session.execute(
                select(Track)
                .options(*_track_eager_options())
                .where(Track.id == track.id)
            ).scalars().unique().first()
            if reloaded is None:
                raise LookupError(f"Track {track.id} disappeared before it could be reloaded")
            session.expunge(reloaded)
            return reloaded
        return None

    def delete(self, track_id: int) -> bool:
        """
        Delete a track by ID

        Args:
            track_id: Track ID to delete

        Returns:
            True if deleted, False if not found OR if the delete failed.

        Note: child rows (fingerprint, similarity-graph edges) are removed by
        the database's ondelete='CASCADE'; the parent-side relationships declare
        passive_deletes=True so SQLAlchemy does not try to NULL their
        non-nullable track_id first (#4598).
        """
        with self._guarded("Failed to delete track") as session:
            try:
                # A single conditional DELETE makes the return value atomic:
                # concurrent callers cannot all observe the row and report
                # success before their individual DELETE statements run
                # (#5173). delete_tracks_by_ids also clears the three association tables
                # (they predate ON DELETE CASCADE) in the same transaction.
                deleted_rows = delete_tracks_by_ids(session, [track_id])
                session.commit()
                deleted = deleted_rows == 1
                if deleted:
                    debug(f"Deleted track id={track_id}")
                return deleted
            except IntegrityError as e:
                # Distinguished from the generic case because it means a relationship
                # is missing passive_deletes=True (or a new child table was added
                # without ondelete='CASCADE') — a code defect, not a runtime blip.
                # It previously surfaced as an ordinary False, indistinguishable from
                # "track not found", which is why #4598 went unnoticed (#4598).
                session.rollback()
                error(
                    f"Failed to delete track {track_id} — integrity constraint violated. "
                    f"A child relationship likely lacks passive_deletes=True: {e}"
                )
                return False
        return False
