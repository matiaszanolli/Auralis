# -*- coding: utf-8 -*-

"""
Album Repository
~~~~~~~~~~~~~~~

Data access layer for album operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List
from pathlib import Path
from sqlalchemy.orm import Session

from ..models import Album
from ..artwork import create_artwork_extractor


class AlbumRepository:
    """Repository for album database operations"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

        # Initialize artwork extractor
        artwork_dir = Path.home() / ".auralis" / "artwork"
        self.artwork_extractor = create_artwork_extractor(str(artwork_dir))

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_title(self, title: str) -> Optional[Album]:
        """Get album by title with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Album)
                .options(joinedload(Album.artist), joinedload(Album.tracks))
                .filter(Album.title == title)
                .first()
            )
        finally:
            session.close()

    def get_all(self) -> List[Album]:
        """Get all albums with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Album)
                .options(joinedload(Album.artist), joinedload(Album.tracks))
                .order_by(Album.title)
                .all()
            )
        finally:
            session.close()

    def extract_and_save_artwork(self, album_id: int) -> Optional[str]:
        """
        Extract artwork from album's tracks and save it

        Args:
            album_id: Album ID to extract artwork for

        Returns:
            Path to saved artwork, or None if extraction failed
        """
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            album = (
                session.query(Album)
                .options(joinedload(Album.tracks))
                .filter(Album.id == album_id)
                .first()
            )

            if not album or not album.tracks:
                return None

            # Try to extract artwork from the first track
            for track in album.tracks:
                if track.filepath and Path(track.filepath).exists():
                    artwork_path = self.artwork_extractor.extract_artwork(
                        track.filepath, album_id
                    )

                    if artwork_path:
                        # Update album with artwork path
                        album.artwork_path = artwork_path
                        session.commit()
                        session.refresh(album)
                        return artwork_path

            return None

        finally:
            session.close()

    def update_artwork(self, album_id: int, artwork_path: str) -> bool:
        """
        Update album artwork path

        Args:
            album_id: Album ID
            artwork_path: Path to artwork file

        Returns:
            True if updated successfully
        """
        session = self.get_session()
        try:
            album = session.query(Album).filter(Album.id == album_id).first()
            if album:
                album.artwork_path = artwork_path
                session.commit()
                return True
            return False
        finally:
            session.close()

    def delete_artwork(self, album_id: int) -> bool:
        """
        Delete album artwork

        Args:
            album_id: Album ID

        Returns:
            True if deleted successfully
        """
        session = self.get_session()
        try:
            album = session.query(Album).filter(Album.id == album_id).first()
            if album and album.artwork_path:
                # Delete file
                self.artwork_extractor.delete_artwork(album.artwork_path)
                # Clear database reference
                album.artwork_path = None
                session.commit()
                return True
            return False
        finally:
            session.close()
