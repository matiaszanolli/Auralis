"""RepositoryFactory hands every thread the same repository, however many touch it first (#6578).

The lazy getters were ``if not self._x: self._x = X(...)``, safe only if every repository were
created at startup. ``fingerprint_scheduler`` is not: the fingerprint queue's workers all start
together and first-touch it at once, so several instances were built - each with its own claim
cursors starting at 0 (#5310) - and the last assignment won. Every getter now builds under a lock.
"""
import threading
import time

import pytest

import auralis.library.repositories.factory as factory_mod
from auralis.library.repositories.factory import RepositoryFactory

# property name -> the class it builds, as named in the factory module
PROPERTIES = {
    "tracks": "TrackRepository",
    "albums": "AlbumRepository",
    "artists": "ArtistRepository",
    "genres": "GenreRepository",
    "playlists": "PlaylistRepository",
    "fingerprints": "FingerprintRepository",
    "fingerprint_scheduler": "FingerprintSchedulerRepository",
    "fingerprint_stats": "FingerprintStatsRepository",
    "stats": "StatsRepository",
    "settings": "SettingsRepository",
    "processing_jobs": "ProcessingJobRepository",
    "similarity_graph": "SimilarityGraphRepository",
}


class _SlowRepository:
    """A constructor slow enough that racing first readers all see the cache empty."""

    built = 0

    def __init__(self, *_args, **_kwargs):
        type(self).built += 1
        time.sleep(0.02)


def _first_touch_from(threads: int, read):
    barrier = threading.Barrier(threads)
    seen: list = []

    def worker():
        barrier.wait()
        seen.append(read())

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    return seen


@pytest.mark.parametrize("name", sorted(PROPERTIES))
def test_racing_first_readers_all_get_one_instance(monkeypatch, name):
    slow = type(f"Slow{PROPERTIES[name]}", (_SlowRepository,), {"built": 0})
    monkeypatch.setattr(factory_mod, PROPERTIES[name], slow)
    monkeypatch.setattr(factory_mod, "AlbumRepository", type("SlowAlbum", (_SlowRepository,), {"built": 0}))
    if name == "albums":
        slow = factory_mod.AlbumRepository
    factory = RepositoryFactory(session_factory=lambda: None)

    seen = _first_touch_from(16, lambda: getattr(factory, name))

    assert len({id(repo) for repo in seen}) == 1
    assert slow.built == 1


def test_the_real_fingerprint_scheduler_is_shared(tmp_path):
    """The issue's own case, with the real class: one instance, so one set of claim cursors."""
    factory = RepositoryFactory(session_factory=lambda: None)

    seen = _first_touch_from(16, lambda: factory.fingerprint_scheduler)

    assert len({id(repo) for repo in seen}) == 1


def test_tracks_still_gets_the_shared_album_repository(monkeypatch):
    monkeypatch.setattr(factory_mod, "AlbumRepository", type("SlowAlbum", (_SlowRepository,), {"built": 0}))
    factory = RepositoryFactory(session_factory=lambda: None)

    tracks = factory.tracks

    assert tracks.album_repository is factory.albums
