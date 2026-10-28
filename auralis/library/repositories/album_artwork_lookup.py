"""
Cheap album artwork lookup (#5896).

``AlbumRepository.get_by_id`` eager-loads the artist, every track and each track's genres,
artists and album, then expunges the lot. The artwork route needs one column, and because its
responses are ``Cache-Control: no-cache`` every thumbnail mount runs a conditional request that
executed that whole query just to answer 304.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from sqlalchemy import select

from ..models import Album
from .base import BaseRepository


class AlbumArtworkLookupMixin(BaseRepository):
    """Single-column artwork read for AlbumArtworkMixin."""

    def get_artwork_path(self, album_id: int) -> tuple[bool, str | None]:
        """``(album exists, its artwork_path)`` from a single-column SELECT; no entity is loaded."""
        with self._session_scope() as session:
            row = session.execute(
                select(Album.artwork_path).where(Album.id == album_id)
            ).first()
            return (row is not None, row[0] if row is not None else None)
