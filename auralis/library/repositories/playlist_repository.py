# -*- coding: utf-8 -*-

"""
Playlist Repository
~~~~~~~~~~~~~~~~~~

Data access layer for playlist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, selectinload

from ..models import Playlist, Track
from ...utils.logging import info, error, debug


class PlaylistRepository:
    """Repository for playlist database operations"""

    def __init__(self, session_factory):
        """
        Initialize playlist repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def create(self, name: str, description: str = "", track_ids: List[int] = None) -> Optional[Playlist]:
        """
        Create a new playlist

        Args:
            name: Playlist name
            description: Playlist description
            track_ids: List of track IDs to add

        Returns:
            Playlist object if successful
        """
        session = self.get_session()
        try:
            playlist = Playlist(name=name, description=description)

            # Add tracks if provided
            if track_ids:
                tracks = session.query(Track).filter(Track.id.in_(track_ids)).all()
                playlist.tracks = tracks

            session.add(playlist)
            session.commit()

            # Get the playlist with eager loading
            playlist = session.query(Playlist).options(
                selectinload(Playlist.tracks).selectinload(Track.artists),
                selectinload(Playlist.tracks).selectinload(Track.genres),
                selectinload(Playlist.tracks).selectinload(Track.album)
            ).filter_by(id=playlist.id).first()

            # Expunge from session to avoid DetachedInstanceError
            session.expunge(playlist)

            info(f"Created playlist: {name}")
            return playlist

        except Exception as e:
            session.rollback()
            error(f"Failed to create playlist: {e}")
            return None
        finally:
            session.close()

    def get_by_id(self, playlist_id: int) -> Optional[Playlist]:
        """Get playlist by ID with eager loading"""
        session = self.get_session()
        try:
            playlist = session.query(Playlist).options(
                selectinload(Playlist.tracks).selectinload(Track.artists),
                selectinload(Playlist.tracks).selectinload(Track.genres),
                selectinload(Playlist.tracks).selectinload(Track.album)
            ).filter(Playlist.id == playlist_id).first()

            if playlist:
                session.expunge(playlist)
            return playlist
        finally:
            session.close()

    def get_all(self) -> List[Playlist]:
        """Get all playlists"""
        session = self.get_session()
        try:
            playlists = session.query(Playlist).order_by(Playlist.name).all()
            # Expunge all playlists to avoid DetachedInstanceError
            for playlist in playlists:
                session.expunge(playlist)
            return playlists
        finally:
            session.close()

    def update(self, playlist_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Update playlist

        Args:
            playlist_id: ID of playlist to update
            update_data: Dictionary with fields to update

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return False

            # Update allowed fields
            for key in ['name', 'description']:
                if key in update_data:
                    setattr(playlist, key, update_data[key])

            session.commit()
            info(f"Updated playlist: {playlist.name}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to update playlist: {e}")
            return False
        finally:
            session.close()

    def delete(self, playlist_id: int) -> bool:
        """
        Delete playlist

        Args:
            playlist_id: ID of playlist to delete

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return False

            session.delete(playlist)
            session.commit()
            info(f"Deleted playlist: {playlist.name}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to delete playlist: {e}")
            return False
        finally:
            session.close()

    def add_track(self, playlist_id: int, track_id: int) -> bool:
        """Add track to playlist"""
        session = self.get_session()
        try:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            track = session.query(Track).filter(Track.id == track_id).first()

            if not playlist or not track:
                return False

            if track not in playlist.tracks:
                playlist.tracks.append(track)
                session.commit()
                debug(f"Added track to playlist: {playlist.name}")

            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to add track to playlist: {e}")
            return False
        finally:
            session.close()

    def remove_track(self, playlist_id: int, track_id: int) -> bool:
        """Remove track from playlist"""
        session = self.get_session()
        try:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            track = session.query(Track).filter(Track.id == track_id).first()

            if not playlist or not track:
                return False

            if track in playlist.tracks:
                playlist.tracks.remove(track)
                session.commit()
                debug(f"Removed track from playlist: {playlist.name}")

            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to remove track from playlist: {e}")
            return False
        finally:
            session.close()

    def clear(self, playlist_id: int) -> bool:
        """Remove all tracks from playlist"""
        session = self.get_session()
        try:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return False

            playlist.tracks = []
            session.commit()
            info(f"Cleared playlist: {playlist.name}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to clear playlist: {e}")
            return False
        finally:
            session.close()
