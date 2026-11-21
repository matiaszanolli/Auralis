"""
Repository Factory for Dependency Injection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides centralized factory for creating and caching repository instances.
Enables dependency injection across the application without global singletons.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from .album_repository import AlbumRepository
from .artist_repository import ArtistRepository
from .fingerprint_repository import FingerprintRepository
from .fingerprint_scheduler_repository import FingerprintSchedulerRepository
from .fingerprint_stats_repository import FingerprintStatsRepository
from .genre_repository import GenreRepository
from .playlist_repository import PlaylistRepository
from .processing_job_repository import ProcessingJobRepository
from .settings_repository import SettingsRepository
from .similarity_graph_repository import SimilarityGraphRepository
from .stats_repository import StatsRepository
from .track_repository import TrackRepository

_Repo = TypeVar("_Repo")


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
        Every thread gets the same instance of each repository, however many touch it first at once.
        Repositories are NOT all created at startup: the fingerprint queue's workers first touch
        ``fingerprint_scheduler`` together, and each private copy started its claim cursors at 0
        (#5310's cursors live on the one per-process instance), so the lazy getters go through a
        double-checked lock (#6578). Creation stays lazy rather than eager because
        ``AlbumRepository`` creates the artwork directory on construction.
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
        # Re-entrant: building `tracks` reads `albums` under the same lock.
        self._create_lock = threading.RLock()

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
        self._processing_job_repo: ProcessingJobRepository | None = None
        self._similarity_graph_repo: SimilarityGraphRepository | None = None

    def _cached(self, attr: str, build: Callable[[], _Repo]) -> _Repo:
        """The repository cached in ``attr``, built once under the lock however many threads ask."""
        repo: _Repo | None = getattr(self, attr)
        if repo is None:
            with self._create_lock:
                repo = getattr(self, attr)
                if repo is None:
                    repo = build()
                    setattr(self, attr, repo)
        return repo

    @property
    def tracks(self) -> TrackRepository:
        return self._cached("_track_repo", lambda: TrackRepository(self.session_factory, album_repository=self.albums))

    @property
    def albums(self) -> AlbumRepository:
        return self._cached("_album_repo", lambda: AlbumRepository(self.session_factory))

    @property
    def artists(self) -> ArtistRepository:
        return self._cached("_artist_repo", lambda: ArtistRepository(self.session_factory))

    @property
    def genres(self) -> GenreRepository:
        return self._cached("_genre_repo", lambda: GenreRepository(self.session_factory))

    @property
    def playlists(self) -> PlaylistRepository:
        return self._cached("_playlist_repo", lambda: PlaylistRepository(self.session_factory))

    @property
    def fingerprints(self) -> FingerprintRepository:
        return self._cached("_fingerprint_repo", lambda: FingerprintRepository(self.session_factory))

    @property
    def fingerprint_scheduler(self) -> FingerprintSchedulerRepository:
        return self._cached("_fingerprint_scheduler_repo", lambda: FingerprintSchedulerRepository(self.session_factory))

    @property
    def fingerprint_stats(self) -> FingerprintStatsRepository:
        return self._cached("_fingerprint_stats_repo", lambda: FingerprintStatsRepository(self.session_factory))

    @property
    def stats(self) -> StatsRepository:
        return self._cached("_stats_repo", lambda: StatsRepository(self.session_factory))

    @property
    def settings(self) -> SettingsRepository:
        return self._cached("_settings_repo", lambda: SettingsRepository(self.session_factory))

    @property
    def processing_jobs(self) -> ProcessingJobRepository:
        return self._cached("_processing_job_repo", lambda: ProcessingJobRepository(self.session_factory))

    @property
    def similarity_graph(self) -> SimilarityGraphRepository:
        return self._cached("_similarity_graph_repo", lambda: SimilarityGraphRepository(self.session_factory))

    def reset_library(self) -> None:
        """Atomically delete the entire library in a single transaction.

        Removes all tracks, fingerprints, playlists, albums, artists, genres,
        and their association rows. Keeps the bulk
        delete inside the repository layer so routers never construct a raw
        session (#4111). Callers must pause background workers first so no rows
        are inserted between the deletes and the commit.

        Deletion order respects foreign keys: association tables and child rows
        before their parents.
        """
        from sqlalchemy import delete

        from ..models import (
            Album,
            Artist,
            Genre,
            Playlist,
            Track,
            track_artist,
            track_genre,
            track_playlist,
        )
        from ..models.fingerprint import TrackFingerprint

        session = self.session_factory()
        try:
            session.execute(track_playlist.delete())
            session.execute(track_genre.delete())
            session.execute(track_artist.delete())

            session.execute(delete(TrackFingerprint))
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
