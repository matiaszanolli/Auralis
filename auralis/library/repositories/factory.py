"""
Repository Factory for Dependency Injection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides centralized factory for creating and caching repository instances.
Enables dependency injection across the application without global singletons.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from .album_repository import AlbumRepository
from .artist_repository import ArtistRepository
from .fingerprint_repository import FingerprintRepository
from .fingerprint_scheduler_repository import FingerprintSchedulerRepository
from .fingerprint_stats_repository import FingerprintStatsRepository
from .genre_repository import GenreRepository
from .playlist_repository import PlaylistRepository
from .queue_history_repository import QueueHistoryRepository
from .queue_repository import QueueRepository
from .queue_template_repository import QueueTemplateRepository
from .settings_repository import SettingsRepository
from .stats_repository import StatsRepository
from .track_repository import TrackRepository


class RepositoryFactory:
    """
    Factory for creating and caching repository instances.

    Provides lazy initialization and caching of repositories via properties.
    Ensures all repositories share the same session factory for consistency.

    Example:
        ```python
        # In startup
        session_factory = sessionmaker(engine)
        repository_factory = RepositoryFactory(session_factory)

        # In routers (dependency injection)
        def get_tracks():
            repos = get_repository_factory()
            tracks, total = repos.tracks.get_all(limit=50)
            return {"tracks": tracks, "total": total}
        ```

    Thread Safety:
        Lazy properties are not thread-safe for initial creation, but since
        repositories are typically created during application startup (before
        concurrent requests), this is not a concern in practice.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        """
        Initialize repository factory.

        Args:
            session_factory: Callable that returns a new SQLAlchemy Session
        """
        self.session_factory = session_factory

        # Lazy initialization caches for all repositories
        self._track_repo: TrackRepository | None = None
        self._album_repo: AlbumRepository | None = None
        self._artist_repo: ArtistRepository | None = None
        self._genre_repo: GenreRepository | None = None
        self._playlist_repo: PlaylistRepository | None = None
        self._fingerprint_repo: FingerprintRepository | None = None
        self._fingerprint_scheduler_repo: FingerprintSchedulerRepository | None = None
        self._fingerprint_stats_repo: FingerprintStatsRepository | None = None
        self._stats_repo: StatsRepository | None = None
        self._settings_repo: SettingsRepository | None = None
        self._queue_repo: QueueRepository | None = None
        self._queue_history_repo: QueueHistoryRepository | None = None
        self._queue_template_repo: QueueTemplateRepository | None = None

    @property
    def tracks(self) -> TrackRepository:
        """Get or create TrackRepository instance (lazy initialization)."""
        if not self._track_repo:
            self._track_repo = TrackRepository(
                self.session_factory,
                album_repository=self.albums
            )
        return self._track_repo

    @property
    def albums(self) -> AlbumRepository:
        """Get or create AlbumRepository instance (lazy initialization)."""
        if not self._album_repo:
            self._album_repo = AlbumRepository(self.session_factory)
        return self._album_repo

    @property
    def artists(self) -> ArtistRepository:
        """Get or create ArtistRepository instance (lazy initialization)."""
        if not self._artist_repo:
            self._artist_repo = ArtistRepository(self.session_factory)
        return self._artist_repo

    @property
    def genres(self) -> GenreRepository:
        """Get or create GenreRepository instance (lazy initialization)."""
        if not self._genre_repo:
            self._genre_repo = GenreRepository(self.session_factory)
        return self._genre_repo

    @property
    def playlists(self) -> PlaylistRepository:
        """Get or create PlaylistRepository instance (lazy initialization)."""
        if not self._playlist_repo:
            self._playlist_repo = PlaylistRepository(self.session_factory)
        return self._playlist_repo

    @property
    def fingerprints(self) -> FingerprintRepository:
        """Get or create FingerprintRepository instance (lazy initialization)."""
        if not self._fingerprint_repo:
            self._fingerprint_repo = FingerprintRepository(self.session_factory)
        return self._fingerprint_repo

    @property
    def fingerprint_scheduler(self) -> FingerprintSchedulerRepository:
        """Get or create FingerprintSchedulerRepository instance (lazy initialization)."""
        if not self._fingerprint_scheduler_repo:
            self._fingerprint_scheduler_repo = FingerprintSchedulerRepository(self.session_factory)
        return self._fingerprint_scheduler_repo

    @property
    def fingerprint_stats(self) -> FingerprintStatsRepository:
        """Get or create FingerprintStatsRepository instance (lazy initialization)."""
        if not self._fingerprint_stats_repo:
            self._fingerprint_stats_repo = FingerprintStatsRepository(self.session_factory)
        return self._fingerprint_stats_repo

    @property
    def stats(self) -> StatsRepository:
        """Get or create StatsRepository instance (lazy initialization)."""
        if not self._stats_repo:
            self._stats_repo = StatsRepository(self.session_factory)
        return self._stats_repo

    @property
    def settings(self) -> SettingsRepository:
        """Get or create SettingsRepository instance (lazy initialization)."""
        if not self._settings_repo:
            self._settings_repo = SettingsRepository(self.session_factory)
        return self._settings_repo

    @property
    def queue(self) -> QueueRepository:
        """Get or create QueueRepository instance (lazy initialization)."""
        if not self._queue_repo:
            self._queue_repo = QueueRepository(self.session_factory)
        return self._queue_repo

    @property
    def queue_history(self) -> QueueHistoryRepository:
        """Get or create QueueHistoryRepository instance (lazy initialization)."""
        if not self._queue_history_repo:
            self._queue_history_repo = QueueHistoryRepository(self.session_factory)
        return self._queue_history_repo

    @property
    def queue_templates(self) -> QueueTemplateRepository:
        """Get or create QueueTemplateRepository instance (lazy initialization)."""
        if not self._queue_template_repo:
            self._queue_template_repo = QueueTemplateRepository(self.session_factory)
        return self._queue_template_repo

    def reset_library(self) -> None:
        """Atomically delete the entire library in a single transaction.

        Removes all tracks, fingerprints, queue state/history, playlists,
        albums, artists, genres, and their association rows. Keeps the bulk
        delete inside the repository layer so routers never construct a raw
        session (#4111). Callers must pause background workers first so no rows
        are inserted between the deletes and the commit.

        Deletion order respects foreign keys: association tables and child rows
        before their parents.
        """
        from sqlalchemy import delete

        from ..models.base import track_artist, track_genre, track_playlist
        from ..models.core import (
            Album,
            Artist,
            Genre,
            Playlist,
            QueueHistory,
            QueueState,
            Track,
        )
        from ..models.fingerprint import TrackFingerprint

        session = self.session_factory()
        try:
            session.execute(track_playlist.delete())
            session.execute(track_genre.delete())
            session.execute(track_artist.delete())

            session.execute(delete(TrackFingerprint))
            session.execute(delete(QueueHistory))
            session.execute(delete(QueueState))
            session.execute(delete(Track))
            session.execute(delete(Playlist))
            session.execute(delete(Album))
            session.execute(delete(Artist))
            session.execute(delete(Genre))

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
