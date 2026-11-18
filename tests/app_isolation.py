"""Fixtures that keep a test which boots ``main.app`` off the developer's real ``~/.auralis``.

``TestClient(app)`` used as a context manager runs the real lifespan: ``LibraryDatabase()`` opens
``DEFAULT_DB_PATH`` (migrating it and writing a backup beside it), the background workers and
auto-scanner start against whatever scan folders it holds, and a library reset or Clear Cache
sweeps the central ``.25d`` fingerprint store. #5810 isolated that for ``tests/backend`` only;
``tests/integration`` booted the same lifespan against the real files (#6441). The definitions
live here, imported by ``tests/conftest.py``, so every directory can use them.

The library DB fixture is opt-in (``client`` requests it). The fingerprint-store one is wired
``autouse`` by the conftest of each directory that boots the app.
"""
import pytest


@pytest.fixture
def _isolated_library_db(tmp_path_factory):
    """Point the library at a throwaway database, a fresh one per test (#5810, #6706).

    ``client`` boots the real startup path, which opens
    ``auralis.library.constants.DEFAULT_DB_PATH`` -- the developer's own
    ``~/.auralis/library.db`` -- migrating it and writing a backup beside it,
    and made every test that wanted "a track from the library" depend on
    whatever that file happened to hold. ``database_engine`` (where the path is
    resolved, since #5837) imported the constant by name, so both bindings are
    patched.

    The database is per test, not per session, because every ``client`` boots a
    lifespan that restarts the fingerprint workers, and they claim every track
    still unfingerprinted. With one session-wide database the upload tests left
    their tracks behind, so each later test's startup and shutdown re-extracted
    the whole backlog: ``test_main_api.py`` went from ~0.1 s a test to ~5 s and
    the file took 18 minutes on CI, which is what pushed the job past its cap.
    A fresh database starts in ~0.06 s.
    """
    import auralis.library.constants as constants
    import auralis.library.database_engine as database_engine

    path = tmp_path_factory.mktemp("auralis_library") / "library.db"
    patcher = pytest.MonkeyPatch()
    patcher.setattr(constants, "DEFAULT_DB_PATH", path)
    patcher.setattr(database_engine, "DEFAULT_DB_PATH", path)
    yield path
    patcher.undo()


@pytest.fixture
def _isolated_fingerprint_store(tmp_path_factory, monkeypatch):
    """A library reset clears the whole central .25d store and Clear Cache sweeps it (#6004); a
    test that boots the app must never do either to the developer's real ~/.auralis/fingerprints."""
    store = tmp_path_factory.mktemp("fingerprint-store")
    monkeypatch.setattr(
        "auralis.analysis.fingerprint.fingerprint_storage.fingerprints_dir", lambda: store
    )
    return store
