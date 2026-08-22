"""
Core Database Models
~~~~~~~~~~~~~~~~~~~~

Core models for tracks, albums, artists, genres, and playlists.

#4511: this module used to define every model class directly; it now
re-exports them from their own per-model modules (`track.py`, `album.py`,
`artist.py`, `genre.py`, `playlist.py`, `queue.py`) so that every existing
`from auralis.library.models.core import X` import keeps working unchanged.
`Base`, `TimestampMixin`, and the association tables are re-exported for the
same reason — callers such as
`auralis.library.repositories.factory.RepositoryFactory` and several tests
import them directly from here.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from ._helpers import _safe_collection, _safe_scalar
from .album import Album
from .artist import Artist
from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist
from .genre import Genre
from .playlist import Playlist
from .queue import QueueHistory, QueueState
from .track import Track

__all__ = [
    # Base
    'Base',
    'TimestampMixin',
    # Association tables
    'track_artist',
    'track_genre',
    'track_playlist',
    # Models
    'Track',
    'Album',
    'Artist',
    'Genre',
    'Playlist',
    'QueueState',
    'QueueHistory',
    # Helpers (#4641) — kept importable from here for back-compat.
    '_safe_collection',
    '_safe_scalar',
]
