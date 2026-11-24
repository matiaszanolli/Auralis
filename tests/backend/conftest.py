"""
Backend Test Configuration

Provides fixtures and configuration for backend testing.
"""

import sys
from pathlib import Path

import pytest

# Add backend to Python path for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(backend_path))


@pytest.fixture(autouse=True)
def _restore_converted_wav_retention():
    """Lifespan shutdown calls converted_wavs.shutdown(), which sets the process-wide registry's
    retention to 0 for good; every later test then decoded a track once per stream instead of
    sharing one conversion (test_seekable_conversion_sharing_5402 failed after any such test)."""
    from core import converted_wav_registry

    converted_wav_registry.converted_wavs._max_idle = converted_wav_registry.IDLE_CONVERSIONS_RETAINED
    yield


@pytest.fixture(autouse=True)
def _reset_rejection_log_throttle():
    """The throttle is process-wide (#6188); a test asserting a rejection log must not be
    silenced by an earlier test that already logged the same reason inside the window."""
    from config import log_throttle

    log_throttle.reset()
    yield
    log_throttle.reset()  # and no flush timer a test armed fires into a later one (#6541)


@pytest.fixture(autouse=True)
def _use_isolated_fingerprint_store(_isolated_fingerprint_store):
    """Every backend test gets the throwaway .25d store (defined in tests/app_isolation.py, #6441)."""


@pytest.fixture(autouse=True)
def _bypass_streaming_path_validation(monkeypatch):
    """Stand in for validate_file_path()'s allowed-directory/is_file/readable
    checks in streaming tests, while still honoring Path.exists() (#4345).

    stream_normal.py / stream_enhanced.py / stream_seek.py now validate
    track.filepath via validate_file_path() before any file I/O. Existing
    tests simulate a present/missing file with fabricated `/tmp/...` paths
    plus `patch.object(Path, "exists", return_value=True/False)`, which
    doesn't satisfy validate_file_path's stricter is_file/readable/
    allowed-directory checks. Those tests exercise message ordering / error
    handling / lifecycle, not the validation boundary itself, so this stand-in
    reproduces the pre-#4345 existence-only check — still driven by the same
    Path.exists() mock each test already sets up. Tests that DO exercise path
    validation (test_streaming_path_validation.py) restore the real function
    explicitly.
    """
    from security.path_security import PathValidationError

    def _existence_only_check(filepath: str, context: str | None = None) -> Path:
        # `context` mirrors the keyword the real validator gained in #4925 so
        # it can log a rejection once, with the caller's context, instead of
        # each caller remembering to. The stand-in accepts and ignores it —
        # without the parameter every streaming test that goes through this
        # fixture dies with "unexpected keyword argument 'context'".
        p = Path(filepath)
        if not p.exists():
            raise PathValidationError(f"File does not exist: {filepath}")
        return p

    monkeypatch.setattr("core.stream_normal.validate_file_path", _existence_only_check)
    monkeypatch.setattr("core.stream_enhanced.validate_file_path", _existence_only_check)
    monkeypatch.setattr("core.stream_seek.validate_file_path", _existence_only_check)


@pytest.fixture
def mock_track():
    """Create a mock track object"""
    from unittest.mock import Mock

    track = Mock()
    track.id = 1
    track.filepath = str(Path(__file__).parent / "fixtures" / "test_audio.mp3")
    track.duration = 238.5
    track.title = "Test Track"
    track.artist = "Test Artist"
    track.album = "Test Album"
    track.album_id = 1

    return track


def _clear_rate_limit_windows() -> None:
    """Clear RateLimitMiddleware's sliding windows (#5089).

    OriginCheckMiddleware is registered outside RateLimitMiddleware precisely
    so a rejected CSRF-shaped request never consumes rate budget. While the
    test client sent no Origin, every state-changing /api request was rejected
    at the origin check and the rate limiter never saw it. Now that the client
    sends a trusted Origin, those requests reach the limiter for real -- and
    the limits are tight (``/api/library/scan`` allows 2 per 60s, uploads 5),
    so either a class with more than two scan tests, or a single test that
    posts more than two payloads to the same endpoint (e.g. a security test
    looping over several malicious inputs), exhausts the budget and gets a 429
    that has nothing to do with what it actually asserts.

    ``main.app`` is a module-level singleton shared by every test in this
    directory, so its middleware instances -- and their windows -- persist for
    the whole session. Clearing them restores isolation without weakening the
    limiter itself, which keeps its own dedicated coverage (see
    test_rate_limit_*.py / test_middleware_429_security_headers.py).
    """
    try:
        import main
    except ImportError:
        return

    stack = getattr(main.app, "middleware_stack", None)
    if stack is None:
        # No request has been served yet, so the stack was never built.
        return

    from config.middleware import RateLimitMiddleware

    node, depth = stack, 0
    while node is not None and depth < 30:
        if isinstance(node, RateLimitMiddleware):
            node._windows.clear()
            node._request_count = 0
            return
        node = getattr(node, "app", None)
        depth += 1


@pytest.fixture(autouse=True)
def _reset_rate_limit_windows():
    """Clear rate-limit state after every test -- see _clear_rate_limit_windows()."""
    yield
    _clear_rate_limit_windows()


@pytest.fixture
def reset_rate_limits():
    """Callable fixture for a test body to reset rate-limit budget mid-test.

    For a single test that deliberately sends more than a rate-limited
    endpoint's per-window allowance -- e.g. looping several malicious payloads
    through the same POST route -- rather than testing the rate limit itself.
    """
    return _clear_rate_limit_windows


@pytest.fixture
def client(_isolated_library_db):
    """
    FastAPI test client for API endpoint testing.

    Returns:
        TestClient: Configured test client with all routes
    """
    import sys
    from pathlib import Path

    from fastapi.testclient import TestClient

    # Import main app
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))
    from main import app
    with TestClient(app) as test_client:
        # Starlette TestClient WebSocket connections use 'testclient' as
        # the host, which the origin-check fix in #3845 correctly rejects
        # (non-loopback empty-Origin).  Patch websocket_connect here so
        # every backend test automatically sends a valid listed Origin
        # without requiring each test to specify it explicitly.
        #
        # #4781: this used to default to http://localhost:3000 (a Vite
        # dev-server origin), which build_ws_origins() only allows when
        # is_dev_mode() is true (#4350) -- and ALLOWED_WS_ORIGINS is
        # frozen once at websocket.connection_manager import time, so no per-test env
        # var/monkeypatch can fix it up after the fact. Since pytest never
        # runs with --dev/AURALIS_DEV_MODE (#4802), every WebSocket-connecting test using
        # this fixture was rejected with "untrusted origin", not hanging
        # as such but failing before any real assertion ran. Port 8765
        # (the backend's own origin) is unconditionally allowlisted
        # regardless of dev/prod mode, so it works no matter when
        # websocket.connection_manager first got imported this session.
        _orig_ws_connect = test_client.websocket_connect

        def _ws_connect_with_origin(url: str, **kwargs):  # type: ignore[override]
            headers = dict(kwargs.pop("headers", {}))
            headers.setdefault("origin", "http://localhost:8765")
            return _orig_ws_connect(url, headers=headers, **kwargs)

        test_client.websocket_connect = _ws_connect_with_origin  # type: ignore[method-assign]

        # #5089: the same reasoning applies to plain HTTP verbs.
        # OriginCheckMiddleware rejects any state-changing /api request
        # that arrives with an empty Origin from a non-loopback host, and
        # Starlette's TestClient reports its host as 'testclient'. Every
        # POST/PUT/DELETE/PATCH built on this fixture therefore got a 403
        # before the route, dependency graph, or Pydantic validator ever
        # ran -- 131 tests across 10 files asserting against a rejection
        # they never intended to exercise. Setting a default Origin on the
        # client (httpx merges these into every request) restores the
        # write-path coverage. The middleware's own enforcement stays
        # covered by test_origin_check_middleware.py, which builds its own
        # app and client rather than using this fixture.
        test_client.headers.update({"origin": "http://localhost:8765"})

        yield test_client


@pytest.fixture
def library_track(client, tmp_path):
    """A real track row in the app's (isolated) library, removed afterwards.

    Gives API tests a track to act on instead of skipping when the library
    they happen to boot against is empty (#5810). The audio file exists on
    disk, so endpoints that read it behave as they would for a scanned track.
    """
    import numpy as np
    import soundfile as sf
    from main import globals_dict

    audio_path = tmp_path / "library_track.wav"
    sf.write(str(audio_path), np.zeros((4410, 2), dtype=np.float32), 44100)

    tracks = globals_dict["library_database"].tracks
    track = tracks.add({
        "title": "Fixture Track",
        "filepath": str(audio_path),
        "artists": ["Fixture Artist"],
        "album": "Fixture Album",
        "format": "WAV",
        "sample_rate": 44100,
        "channels": 2,
        "duration": 0.1,
    })
    assert track is not None, "fixture track could not be inserted"
    yield track
    tracks.delete(track.id)


# ============================================================
# Phase 5C: Mock Repository Fixtures for Dual-Mode Testing
# ============================================================

@pytest.fixture
def mock_library_database():
    """
    A mock LibraryDatabase for testing routers: every repository interface,
    no real database connection.
    """
    from unittest.mock import Mock

    manager = Mock()

    # Mock repositories
    manager.tracks = Mock()
    manager.albums = Mock()
    manager.artists = Mock()
    manager.genres = Mock()
    manager.playlists = Mock()
    manager.fingerprints = Mock()
    manager.stats = Mock()
    manager.settings = Mock()

    # Mock get_all returns (list, total)
    manager.tracks.get_all = Mock(return_value=([], 0))
    manager.albums.get_all = Mock(return_value=([], 0))
    manager.artists.get_all = Mock(return_value=([], 0))
    manager.genres.get_all = Mock(return_value=([], 0))
    manager.playlists.get_all = Mock(return_value=([], 0))

    # Mock search returns (list, total)
    manager.tracks.search = Mock(return_value=([], 0))
    manager.artists.search = Mock(return_value=([], 0))
    manager.albums.search = Mock(return_value=([], 0))

    # Mock individual get_by_id methods
    manager.tracks.get_by_id = Mock(return_value=None)
    manager.albums.get_by_id = Mock(return_value=None)
    manager.artists.get_by_id = Mock(return_value=None)
    manager.artists.get_page = Mock(return_value=None)
    manager.artists.get_track_rows = Mock(return_value=None)
    manager.genres.get_by_id = Mock(return_value=None)
    manager.playlists.get_by_id = Mock(return_value=None)

    # Mock CRUD operations
    manager.tracks.create = Mock(return_value=Mock(id=1))
    manager.tracks.update = Mock(return_value=Mock(id=1))
    manager.tracks.delete = Mock(return_value=True)
    manager.albums.create = Mock(return_value=Mock(id=1))
    manager.artists.create = Mock(return_value=Mock(id=1))

    # Mock cache operations
    manager.clear_cache = Mock()
    manager.get_cache_stats = Mock(return_value={"hits": 0, "misses": 0})

    return manager


@pytest.fixture
def mock_repository_factory():
    """
    Create a mock RepositoryFactory for testing routers.

    This mock provides the repository pattern interface
    without requiring a real database connection.

    Phase 5C: Enables testing endpoints with RepositoryFactory
    while maintaining backward compatibility with LibraryManager tests.
    """
    from unittest.mock import Mock

    factory = Mock()

    # Mock all repositories
    factory.tracks = Mock()
    factory.albums = Mock()
    factory.artists = Mock()
    factory.genres = Mock()
    factory.playlists = Mock()
    factory.fingerprints = Mock()
    factory.fingerprint_stats = Mock()
    factory.stats = Mock()
    factory.settings = Mock()

    # Mock get_all returns (list, total)
    factory.tracks.get_all = Mock(return_value=([], 0))
    factory.albums.get_all = Mock(return_value=([], 0))
    factory.artists.get_all = Mock(return_value=([], 0))
    factory.genres.get_all = Mock(return_value=([], 0))
    factory.playlists.get_all = Mock(return_value=([], 0))

    # Mock search returns (list, total)
    factory.tracks.search = Mock(return_value=([], 0))
    factory.artists.search = Mock(return_value=([], 0))
    factory.albums.search = Mock(return_value=([], 0))

    # Mock individual get_by_id methods
    factory.tracks.get_by_id = Mock(return_value=None)
    factory.albums.get_by_id = Mock(return_value=None)
    factory.artists.get_by_id = Mock(return_value=None)
    factory.artists.get_page = Mock(return_value=None)
    factory.artists.get_track_rows = Mock(return_value=None)
    factory.genres.get_by_id = Mock(return_value=None)
    factory.playlists.get_by_id = Mock(return_value=None)
    factory.fingerprints.get_by_id = Mock(return_value=None)

    # Mock CRUD operations
    factory.tracks.create = Mock(return_value=Mock(id=1))
    factory.tracks.create_batch = Mock(return_value=[Mock(id=i) for i in range(1, 4)])
    factory.tracks.update = Mock(return_value=Mock(id=1))
    factory.tracks.delete = Mock(return_value=True)
    factory.tracks.update_metadata = Mock(return_value=Mock(id=1))
    factory.albums.create = Mock(return_value=Mock(id=1))
    factory.artists.create = Mock(return_value=Mock(id=1))
    factory.genres.create = Mock(return_value=Mock(id=1))

    # Mock query operations
    factory.tracks.get_by_album = Mock(return_value=[])

    # Mock stats/fingerprint operations
    factory.fingerprint_stats.get_fingerprint_stats = Mock(
        return_value={
            'total': 0,
            'fingerprinted': 0,
            'pending': 0,
            'progress_percent': 0
        }
    )
    factory.fingerprint_stats.cleanup_incomplete_fingerprints = Mock(return_value=0)

    # Mock settings operations
    factory.settings.get_all = Mock(return_value={})
    factory.settings.get = Mock(return_value=None)
    factory.settings.set = Mock(return_value=True)

    return factory


# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest with asyncio settings"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
