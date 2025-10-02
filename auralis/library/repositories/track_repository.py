# -*- coding: utf-8 -*-

"""
Track Repository
~~~~~~~~~~~~~~~

Data access layer for track operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from ..models import Track, Artist, Album, Genre
from ...utils.logging import info, warning, error, debug


class TrackRepository:
    """Repository for track database operations"""

    def __init__(self, session_factory):
        """
        Initialize track repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def add(self, track_info: Dict[str, Any]) -> Optional[Track]:
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
            existing = session.query(Track).filter(Track.filepath == track_info['filepath']).first()
            if existing:
                warning(f"Track already exists: {track_info['filepath']}")
                return existing

            # Get or create artist(s)
            artists = []
            for artist_name in track_info.get('artists', []):
                artist = session.query(Artist).filter(Artist.name == artist_name).first()
                if not artist:
                    artist = Artist(name=artist_name)
                    session.add(artist)
                artists.append(artist)

            # Get or create album
            album = None
            if track_info.get('album'):
                album = session.query(Album).filter(
                    Album.title == track_info['album'],
                    Album.artist_id == artists[0].id if artists else None
                ).first()
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

            info(f"Added track: {track.title}")
            return track

        except Exception as e:
            session.rollback()
            error(f"Failed to add track: {e}")
            return None
        finally:
            session.close()

    def get_by_id(self, track_id: int) -> Optional[Track]:
        """Get track by ID"""
        session = self.get_session()
        try:
            return session.query(Track).filter(Track.id == track_id).first()
        finally:
            session.close()

    def get_by_path(self, filepath: str) -> Optional[Track]:
        """Get track by file path"""
        session = self.get_session()
        try:
            return session.query(Track).filter(Track.filepath == filepath).first()
        finally:
            session.close()

    def get_by_filepath(self, filepath: str) -> Optional[Track]:
        """Alias for get_by_path for backward compatibility"""
        return self.get_by_path(filepath)

    def update_by_filepath(self, filepath: str, track_info: Dict[str, Any]) -> Optional[Track]:
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
            info(f"Updated track: {track.title}")
            return track

        except Exception as e:
            session.rollback()
            error(f"Failed to update track: {e}")
            return None
        finally:
            session.close()

    def search(self, query: str, limit: int = 50) -> List[Track]:
        """
        Search tracks by title, artist, album, or genre

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching tracks
        """
        session = self.get_session()
        try:
            search_term = f"%{query}%"
            results = session.query(Track).join(Track.artists).join(Track.album, isouter=True).filter(
                or_(
                    Track.title.ilike(search_term),
                    Artist.name.ilike(search_term),
                    Album.title.ilike(search_term)
                )
            ).limit(limit).all()

            return results
        finally:
            session.close()

    def get_by_genre(self, genre_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by genre"""
        session = self.get_session()
        try:
            genre = session.query(Genre).filter(Genre.name == genre_name).first()
            if not genre:
                return []
            return genre.tracks[:limit]
        finally:
            session.close()

    def get_by_artist(self, artist_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by artist"""
        session = self.get_session()
        try:
            artist = session.query(Artist).filter(Artist.name == artist_name).first()
            if not artist:
                return []
            return artist.tracks[:limit]
        finally:
            session.close()

    def get_recent(self, limit: int = 50) -> List[Track]:
        """Get recently added tracks"""
        session = self.get_session()
        try:
            return session.query(Track).order_by(Track.date_added.desc()).limit(limit).all()
        finally:
            session.close()

    def get_popular(self, limit: int = 50) -> List[Track]:
        """Get most played tracks"""
        session = self.get_session()
        try:
            return session.query(Track).order_by(Track.play_count.desc()).limit(limit).all()
        finally:
            session.close()

    def get_favorites(self, limit: int = 50) -> List[Track]:
        """Get favorite tracks"""
        session = self.get_session()
        try:
            return session.query(Track).filter(Track.favorite == True).order_by(Track.date_modified.desc()).limit(limit).all()
        finally:
            session.close()

    def record_play(self, track_id: int):
        """Record a track play"""
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if track:
                track.play_count = (track.play_count or 0) + 1
                track.last_played = func.now()
                session.commit()
                debug(f"Recorded play for track: {track.title}")
        except Exception as e:
            session.rollback()
            error(f"Failed to record play: {e}")
        finally:
            session.close()

    def set_favorite(self, track_id: int, favorite: bool = True):
        """Set track favorite status"""
        session = self.get_session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            if track:
                track.favorite = favorite
                session.commit()
                debug(f"Set favorite={favorite} for track: {track.title}")
        except Exception as e:
            session.rollback()
            error(f"Failed to set favorite: {e}")
        finally:
            session.close()

    def find_similar(self, track: Track, limit: int = 5) -> List[Track]:
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
                    artist_tracks = session.query(Track).filter(
                        Track.artists.contains(artist),
                        Track.id != track.id
                    ).limit(limit).all()
                    similar_tracks.extend(artist_tracks)

            # Find tracks in same genre
            if track.genres and len(similar_tracks) < limit:
                for genre in track.genres:
                    genre_tracks = session.query(Track).filter(
                        Track.genres.contains(genre),
                        Track.id != track.id
                    ).limit(limit - len(similar_tracks)).all()
                    similar_tracks.extend(genre_tracks)

            return similar_tracks[:limit]
        finally:
            session.close()

    def _update_artists(self, session: Session, track: Track, artist_names: List[str]):
        """Update track artists"""
        track.artists = []
        for artist_name in artist_names:
            artist = session.query(Artist).filter(Artist.name == artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
            track.artists.append(artist)

    def _update_genres(self, session: Session, track: Track, genre_names: List[str]):
        """Update track genres"""
        track.genres = []
        for genre_name in genre_names:
            genre = session.query(Genre).filter(Genre.name == genre_name).first()
            if not genre:
                genre = Genre(name=genre_name)
                session.add(genre)
            track.genres.append(genre)
