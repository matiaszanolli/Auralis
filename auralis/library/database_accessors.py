"""
Repository accessors for LibraryDatabase (split from database.py, #5837).

Conveniences that forward to ``repositories`` so a component that needs one
repository can take the database object and reach it directly.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .repositories import (
    AlbumRepository,
    ArtistRepository,
    FingerprintRepository,
    FingerprintStatsRepository,
    GenreRepository,
    PlaylistRepository,
    RepositoryFactory,
    StatsRepository,
    TrackRepository,
)
from .repositories.settings_repository import SettingsRepository


class RepositoryAccessorsMixin:
    """Forwarding properties; ``repositories`` and ``SessionLocal`` are set by LibraryDatabase.__init__."""

    repositories: RepositoryFactory
    SessionLocal: Any

    @property
    def session_factory(self) -> Any:
        """The SQLAlchemy sessionmaker, under the RepositoryFactory's name."""
        return self.SessionLocal

    @property
    def tracks(self) -> TrackRepository:
        return self.repositories.tracks

    @property
    def albums(self) -> AlbumRepository:
        return self.repositories.albums

    @property
    def artists(self) -> ArtistRepository:
        return self.repositories.artists

    @property
    def genres(self) -> GenreRepository:
        return self.repositories.genres

    @property
    def playlists(self) -> PlaylistRepository:
        return self.repositories.playlists

    @property
    def stats(self) -> StatsRepository:
        return self.repositories.stats

    @property
    def fingerprints(self) -> FingerprintRepository:
        return self.repositories.fingerprints

    @property
    def fingerprint_stats(self) -> FingerprintStatsRepository:
        return self.repositories.fingerprint_stats

    @property
    def settings(self) -> SettingsRepository:
        return self.repositories.settings

    def get_session(self) -> Any:
        """Get a new database session."""
        return self.SessionLocal()
