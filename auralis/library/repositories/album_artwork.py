"""
Album artwork persistence (split from album_repository.py, #5837): extraction
from an album's tracks and the path bookkeeping around it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..artwork import ArtworkExtractor
from ..models import Album
from .base import BaseRepository


class AlbumArtworkMixin(BaseRepository):
    """Artwork methods of AlbumRepository; ``artwork_extractor`` is built by its ``__init__``."""

    artwork_extractor: ArtworkExtractor

    def extract_and_save_artwork(self, album_id: int) -> str | None:
        """
        Extract artwork from album's tracks and save it

        Args:
            album_id: Album ID to extract artwork for

        Returns:
            Path to saved artwork, or None if extraction failed
        """
        with self._session_scope() as session:
            album = session.execute(
                select(Album)
                # Deliberately narrower than _ALBUM_DETAIL_OPTIONS (#5028
                # CONSISTENCY check): only album.tracks is read below, never
                # album.artist, so there's no reason to pay for the join.
                .options(selectinload(Album.tracks))
                .where(Album.id == album_id)
            ).scalars().first()

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
                        previous_path = album.artwork_path
                        album.artwork_path = artwork_path
                        session.commit()
                        session.refresh(album)
                        # Remove the superseded file now that the new path is
                        # committed (mirrors delete_artwork below; #4850).
                        # Every write generates a unique
                        # album_{id}_{content_hash}.ext filename, so leaving
                        # this unlinked orphaned one more file on every
                        # re-extract with no sweeper anywhere to reclaim it.
                        if previous_path and previous_path != artwork_path:
                            self.artwork_extractor.delete_artwork(previous_path)
                        return artwork_path

            return None

    def update_artwork(self, album_id: int, artwork_path: str) -> bool:
        """
        Update album artwork path

        Args:
            album_id: Album ID
            artwork_path: Path to artwork file

        Returns:
            True if updated successfully
        """
        with self._session_scope() as session:
            try:
                album = session.execute(select(Album).where(Album.id == album_id)).scalars().first()
                if album:
                    album.artwork_path = artwork_path
                    session.commit()
                    return True
                return False
            except Exception:
                session.rollback()  # fixes #2238: prevent dirty session in pool
                raise

    def delete_artwork(self, album_id: int) -> bool:
        """
        Delete album artwork

        Args:
            album_id: Album ID

        Returns:
            True if deleted successfully
        """
        with self._session_scope() as session:
            try:
                album = session.execute(select(Album).where(Album.id == album_id)).scalars().first()
                if album and album.artwork_path:
                    # Delete file
                    self.artwork_extractor.delete_artwork(album.artwork_path)
                    # Clear database reference
                    album.artwork_path = None
                    session.commit()
                    return True
                return False
            except Exception:
                session.rollback()  # fixes #2238: prevent dirty session in pool
                raise

    def update_artwork_path(self, album_id: int, artwork_path: str) -> Album | None:
        """
        Update album artwork path.

        Args:
            album_id: Album ID
            artwork_path: Path to artwork file

        Returns:
            Updated album or None if not found

        Raises:
            Exception: If update fails
        """
        with self._session_scope() as session:
            try:
                album = session.execute(select(Album).where(Album.id == album_id)).scalars().first()
                if not album:
                    return None

                previous_path = album.artwork_path
                album.artwork_path = artwork_path
                session.commit()
                session.refresh(album)
                # Every other read path here eager-loads artist + tracks because
                # Album.to_dict() reads both; refresh() does not re-apply query
                # options, so force them in before detaching (#4641). The artwork
                # router hands this album straight to to_dict().
                _ = album.artist, album.tracks
                session.expunge(album)
                # Remove the superseded file now that the new path is
                # committed (mirrors delete_artwork below; #4850) -- the
                # download flow through here left the previous file on disk
                # forever on every re-download that produced different bytes.
                if previous_path and previous_path != artwork_path:
                    self.artwork_extractor.delete_artwork(previous_path)
                return album
            except Exception:
                session.rollback()
                raise
