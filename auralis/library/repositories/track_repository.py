"""
Track Repository
~~~~~~~~~~~~~~~

Data access layer for track operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from ...utils.logging import debug, error, info, warning
from ..models import Album, Artist, Genre, Track
from ..utils.artist_normalizer import normalize_artist_name


class TrackRepository:
    """Repository for track database operations"""

    def __init__(self, session_factory: Callable[[], Session], album_repository: Any | None = None) -> None:
        """
        Initialize track repository

        Args:
            session_factory: SQLAlchemy session factory
            album_repository: AlbumRepository instance for artwork extraction
        """
        self.session_factory = session_factory
        self.album_repository = album_repository

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def add(self, track_info: dict[str, Any]) -> Track | None:
        """
        Add a track to the library

        Args:
            track_info: Dictionary with track information

        Returns:
            Track object if successful, None if failed
        """
        session = self.get_session()
        try:
            # Check if track already exists
            existing = session.query(Track).options(
                joinedload(Track.artists), joinedload(Track.album)
            ).filter(Track.filepath == track_info['filepath']).first()
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

            # Get or create artist(s) using normalized name matching
            artists = []
            for artist_name in track_info.get('artists', []):
                normalized = normalize_artist_name(artist_name)
                # Match by normalized name to prevent duplicates (AC/DC vs ACDC)
                artist = session.query(Artist).filter(
                    Artist.normalized_name == normalized
                ).first()
                if not artist:
                    artist = Artist(name=artist_name, normalized_name=normalized)
                    session.add(artist)
                artists.append(artist)

            # Get or create album
            album = None
            if track_info.get('album'):
                album_filter = Album.title == track_info['album']
                if artists:
                    album_filter = and_(album_filter, Album.artist_id == artists[0].id)
                album = session.query(Album).filter(album_filter).first()
                if not album and artists:
                    album = Album(
                        title=track_info['album'],
                        artist_id=artists[0].id,
                        year=track_info.get('year')
                    )
                    session.add(album)

            # Get or create genres
            genres = []
            for genre_name in track_info.get('genres', []):
                genre = session.query(Genre).filter(Genre.name == genre_name).first()
                if not genre:
                    genre = Genre(name=genre_name)
                    session.add(genre)
                genres.append(genre)

            # Create track
            track = Track(
                title=track_info.get('title', 'Unknown'),
                filepath=track_info['filepath'],
                duration=track_info.get('duration'),
                sample_rate=track_info.get('sample_rate'),
                bit_depth=track_info.get('bit_depth'),
                channels=track_info.get('channels'),
                format=track_info.get('format'),
                filesize=track_info.get('filesize'),
                peak_level=track_info.get('peak_level'),
                rms_level=track_info.get('rms_level'),
                dr_rating=track_info.get('dr_rating'),
                lufs_level=track_info.get('lufs_level'),
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
            track = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.id == track.id)
                .first()
            )
            session.expunge(track)
            return track

        except Exception as e:
            session.rollback()
            error(f"Failed to add track: {e}")
            return None
        finally:
            session.close()

    def get_by_id(self, track_id: int) -> Track | None:
        """Get track by ID with relationships loaded"""
        session = self.get_session()
        try:
            track = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.id == track_id)
                .first()
            )
            if track:
                session.expunge(track)
            return track
        finally:
            session.close()

    def get_by_path(self, filepath: str) -> Track | None:
        """Get track by file path with relationships loaded"""
        session = self.get_session()
        try:
            track = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.filepath == filepath)
                .first()
            )
            if track:
                session.expunge(track)
            return track
        finally:
            session.close()

    def get_by_filepath(self, filepath: str) -> Track | None:
        """Alias for get_by_path for backward compatibility"""
        return self.get_by_path(filepath)

    def update_by_filepath(self, filepath: str, track_info: dict[str, Any]) -> Track | None:
        """
        Update track by filepath

        Args:
            filepath: Path to track file
            track_info: Dictionary with updated track information

        Returns:
            Updated Track object if successful, None if failed
        """
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.filepath == filepath).first()
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
                album = session.query(Album).filter(Album.title == track_info['album']).first()
                if not album:
                    album = Album(title=track_info['album'], year=track_info.get('year'))
                    session.add(album)
                track.album = album

            session.commit()
            # Re-query with eager loading before detaching from session
            track = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.filepath == filepath)
                .first()
            )
            info(f"Updated track: {track.title}")
            session.expunge(track)
            return track

        except Exception as e:
            session.rollback()
            error(f"Failed to update track: {e}")
            return None
        finally:
            session.close()

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """
        Search tracks by title, artist, album, or genre

        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Number of results to skip (for pagination)

        Returns:
            Tuple of (matching tracks, total count)
        """
        session = self.get_session()
        try:
            search_term = f"%{query}%"

            # Build query with outer joins to include tracks without artists/albums
            query_obj = (
                session.query(Track)
                .join(Track.artists, isouter=True)
                .join(Track.album, isouter=True)
                .options(selectinload(Track.artists), selectinload(Track.album))
                .filter(
                    or_(
                        Track.title.ilike(search_term),
                        Artist.name.ilike(search_term),
                        Album.title.ilike(search_term)
                    )
                )
                .distinct()
            )

            # Get total count
            total = query_obj.count()

            # Get paginated results
            results = query_obj.limit(limit).offset(offset).all()

            for track in results:
                session.expunge(track)
            return results, total
        finally:
            session.close()

    def get_by_genre(self, genre_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by genre"""
        session = self.get_session()
        try:
            tracks = (
                session.query(Track)
                .join(Track.genres)
                .options(selectinload(Track.artists), selectinload(Track.album))
                .filter(Genre.name == genre_name)
                .limit(limit)
                .all()
            )
            for track in tracks:
                session.expunge(track)
            return tracks
        finally:
            session.close()

    def get_by_artist(self, artist_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by artist"""
        session = self.get_session()
        try:
            # Use eager loading to load relationships before session closes
            tracks = session.query(Track).join(Track.artists).filter(
                Artist.name == artist_name
            ).options(
                joinedload(Track.artists),
                joinedload(Track.album),
                joinedload(Track.genres)
            ).limit(limit).all()

            # Expunge from session to make objects persistent across session close
            for track in tracks:
                session.expunge(track)

            return tracks
        finally:
            session.close()

    def get_recent(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get recently added tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        session = self.get_session()
        try:
            # Build query
            query = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .order_by(Track.created_at.desc())
            )

            # Get total count
            total = query.count()

            # Get paginated results
            results = query.limit(limit).offset(offset).all()

            for track in results:
                session.expunge(track)
            return results, total
        finally:
            session.close()

    def get_popular(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get most played tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        session = self.get_session()
        try:
            # Build query
            query = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .order_by(Track.play_count.desc())
            )

            # Get total count
            total = query.count()

            # Get paginated results
            results = query.limit(limit).offset(offset).all()

            for track in results:
                session.expunge(track)
            return results, total
        finally:
            session.close()

    def get_favorites(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get favorite tracks with relationships loaded

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)

        Returns:
            Tuple of (track list, total count)
        """
        session = self.get_session()
        try:
            # Build query
            query = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.favorite == True)
                .order_by(Track.title.asc())
            )

            # Get total count
            total = query.count()

            # Get paginated results
            results = query.limit(limit).offset(offset).all()

            for track in results:
                session.expunge(track)
            return results, total
        finally:
            session.close()

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Track], int]:
        """Get all tracks with pagination and total count

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip (for pagination)
            order_by: Column name to order by ('title', 'created_at', 'play_count', etc.)

        Returns:
            Tuple of (list of Track objects, total count)
        """
        session = self.get_session()
        try:
            # Get total count
            total = session.query(Track).count()

            # Get tracks for current page
            order_column = getattr(Track, order_by, Track.title)
            tracks = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .order_by(order_column.asc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            for track in tracks:
                session.expunge(track)
            return tracks, total
        finally:
            session.close()

    def record_play(self, track_id: int) -> None:
        """Record a track play"""
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if track:
                track.play_count = (track.play_count or 0) + 1  # type: ignore[assignment]
                track.last_played = func.now()  # type: ignore[assignment]
                session.commit()
                debug(f"Recorded play for track: {track.title}")
        except Exception as e:
            session.rollback()
            error(f"Failed to record play: {e}")
        finally:
            session.close()

    def set_favorite(self, track_id: int, favorite: bool = True) -> None:
        """Set track favorite status"""
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if track:
                track.favorite = favorite  # type: ignore[assignment]
                session.commit()
                debug(f"Set favorite={favorite} for track: {track.title}")
        except Exception as e:
            session.rollback()
            error(f"Failed to set favorite: {e}")
        finally:
            session.close()

    def find_similar(self, track: Track, limit: int = 5) -> list[Track]:
        """
        Find similar tracks based on audio characteristics

        Args:
            track: Reference track
            limit: Maximum number of results

        Returns:
            List of similar tracks
        """
        session = self.get_session()
        try:
            # Simple similarity based on genre and artist
            # In production, would use more sophisticated audio fingerprinting
            similar_tracks = []

            # Find tracks by same artist
            if track.artists:
                for artist in track.artists:
                    artist_tracks = (
                        session.query(Track)
                        .options(selectinload(Track.artists), selectinload(Track.album))
                        .filter(Track.artists.contains(artist), Track.id != track.id)
                        .limit(limit)
                        .all()
                    )
                    similar_tracks.extend(artist_tracks)

            # Find tracks in same genre
            if track.genres and len(similar_tracks) < limit:
                for genre in track.genres:
                    genre_tracks = (
                        session.query(Track)
                        .options(selectinload(Track.artists), selectinload(Track.album))
                        .filter(Track.genres.contains(genre), Track.id != track.id)
                        .limit(limit - len(similar_tracks))
                        .all()
                    )
                    similar_tracks.extend(genre_tracks)

            result = similar_tracks[:limit]
            for t in set(result):
                session.expunge(t)
            return result
        finally:
            session.close()

    def _update_artists(self, session: Session, track: Track, artist_names: list[str]) -> None:
        """Update track artists using normalized name matching"""
        track.artists = []
        for artist_name in artist_names:
            normalized = normalize_artist_name(artist_name)
            # Match by normalized name to prevent duplicates (AC/DC vs ACDC)
            artist = session.query(Artist).filter(
                Artist.normalized_name == normalized
            ).first()
            if not artist:
                artist = Artist(name=artist_name, normalized_name=normalized)
                session.add(artist)
            track.artists.append(artist)

    def _update_genres(self, session: Session, track: Track, genre_names: list[str]) -> None:
        """Update track genres"""
        track.genres = []
        for genre_name in genre_names:
            genre = session.query(Genre).filter(Genre.name == genre_name).first()
            if not genre:
                genre = Genre(name=genre_name)
                session.add(genre)
            track.genres.append(genre)

    def delete(self, track_id: int) -> bool:
        """
        Delete a track by ID

        Args:
            track_id: Track ID to delete

        Returns:
            True if deleted, False if not found
        """
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if track:
                session.delete(track)
                session.commit()
                debug(f"Deleted track: {track.title}")
                return True
            return False
        except Exception as e:
            session.rollback()
            error(f"Failed to delete track: {e}")
            return False
        finally:
            session.close()

    def update(self, track_id: int, track_info: dict[str, Any]) -> Track | None:
        """
        Update a track by ID

        Args:
            track_id: Track ID to update
            track_info: Dictionary with updated track information

        Returns:
            Updated track or None if not found
        """
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
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
                    album = session.query(Album).filter(Album.title == album_title).first()
                    if not album:
                        album = Album(title=album_title)
                        session.add(album)
                    track.album = album

            session.commit()
            # Re-query with eager loading before detaching from session
            track = (
                session.query(Track)
                .options(joinedload(Track.artists), joinedload(Track.album))
                .filter(Track.id == track_id)
                .first()
            )
            debug(f"Updated track: {track.title}")
            session.expunge(track)
            return track
        except Exception as e:
            session.rollback()
            error(f"Failed to update track: {e}")
            return None
        finally:
            session.close()

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
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if not track:
                return None

            # Update only provided fields
            for key, value in fields.items():
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
        finally:
            session.close()

    def cleanup_missing_files(self, batch_size: int = 1000) -> int:
        """
        Remove tracks with missing audio files from the database.

        Processes in batches to keep memory bounded regardless of library size.

        Args:
            batch_size: Number of tracks to load per batch

        Returns:
            Number of tracks removed

        Raises:
            Exception: If cleanup fails
        """
        import os

        session = self.get_session()
        try:
            removed_count = 0
            offset = 0

            while True:
                rows = (
                    session.query(Track.id, Track.filepath)
                    .order_by(Track.id)
                    .offset(offset)
                    .limit(batch_size)
                    .all()
                )
                if not rows:
                    break

                missing_ids = [
                    row.id for row in rows
                    if not os.path.exists(row.filepath)
                ]

                if missing_ids:
                    session.query(Track).filter(
                        Track.id.in_(missing_ids)
                    ).delete(synchronize_session=False)
                    session.commit()
                    removed_count += len(missing_ids)

                offset += batch_size

            debug(f"Removed {removed_count} tracks with missing files")
            return removed_count
        except Exception as e:
            session.rollback()
            error(f"Failed to cleanup missing files: {e}")
            raise
        finally:
            session.close()
