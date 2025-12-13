"""
Backend Test Configuration

Provides fixtures and configuration for backend testing.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add backend to Python path for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests.

    This fixture ensures pytest-asyncio works correctly.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


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


@pytest.fixture
def sample_audio():
    """
    Generate sample audio data for testing.

    Returns:
        tuple: (audio_data, sample_rate)
            - audio_data: numpy array (samples, channels) for stereo
            - sample_rate: int (44100)
    """
    import numpy as np

    sample_rate = 44100
    duration = 1.0  # 1 second
    samples = int(sample_rate * duration)

    # Generate 440 Hz sine wave (A4 note)
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    return audio_stereo, sample_rate


@pytest.fixture
def sample_audio_long():
    """
    Generate longer sample audio (30 seconds) for chunk testing.

    Returns:
        tuple: (audio_data, sample_rate)
    """
    import numpy as np

    sample_rate = 44100
    duration = 30.0  # 30 seconds
    samples = int(sample_rate * duration)

    # Generate 440 Hz sine wave
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    return audio_stereo, sample_rate


@pytest.fixture
def client():
    """
    FastAPI test client for API endpoint testing.

    Returns:
        TestClient: Configured test client with all routes
    """
    from fastapi.testclient import TestClient
    import sys
    from pathlib import Path

    # Import main app
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))
    try:
        from main import app
        with TestClient(app) as test_client:
            yield test_client
    except ImportError:
        # If backend not available, skip fixture
        pytest.skip("Backend main app not available")


@pytest.fixture
def sample_track_ids(client, mock_track):
    """
    Create sample tracks in the database for testing.

    Returns:
        list: List of track IDs [1, 2, 3]
    """
    # For now, return mock track IDs
    # In a real implementation, this would create tracks in test database
    return [1, 2, 3]


@pytest.fixture
def fingerprint_count():
    """
    Return the number of fingerprints in test database.

    Returns:
        int: Number of fingerprints (mock value for testing)
    """
    # For now, return a mock value
    # In a real implementation, this would query the test database
    return 100


# ============================================================
# Phase 5C: Mock Repository Fixtures for Dual-Mode Testing
# ============================================================

@pytest.fixture
def mock_library_manager():
    """
    Create a mock LibraryManager for testing routers.

    This mock provides all necessary repository interfaces
    without requiring a real database connection.
    """
    from unittest.mock import Mock, MagicMock

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
    from unittest.mock import Mock, MagicMock

    factory = Mock()

    # Mock all repositories
    factory.tracks = Mock()
    factory.albums = Mock()
    factory.artists = Mock()
    factory.genres = Mock()
    factory.playlists = Mock()
    factory.fingerprints = Mock()
    factory.stats = Mock()
    factory.settings = Mock()
    factory.queue = Mock()
    factory.queue_history = Mock()
    factory.queue_templates = Mock()

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
    factory.tracks.get_by_artist = Mock(return_value=[])
    factory.tracks.get_by_album = Mock(return_value=[])
    factory.albums.get_by_artist = Mock(return_value=[])

    # Mock stats/fingerprint operations
    factory.fingerprints.get_fingerprint_stats = Mock(
        return_value={
            'total': 0,
            'fingerprinted': 0,
            'pending': 0,
            'progress_percent': 0
        }
    )
    factory.fingerprints.get_fingerprint_status = Mock(return_value=None)
    factory.fingerprints.cleanup_incomplete_fingerprints = Mock(return_value=0)

    # Mock settings operations
    factory.settings.get_all = Mock(return_value={})
    factory.settings.get = Mock(return_value=None)
    factory.settings.set = Mock(return_value=True)

    return factory


@pytest.fixture
def mock_repository_factory_callable(mock_repository_factory):
    """Return a callable that provides mock RepositoryFactory (for DI pattern).

    This fixture enables dependency injection pattern for testing router endpoints
    with mock repositories. Use this to test components that accept a callable
    returning a RepositoryFactory.

    Phase 5A.2: Mock variant for backend API router testing.

    Args:
        mock_repository_factory: Mock RepositoryFactory fixture

    Returns:
        Callable: Function that returns the mock RepositoryFactory instance

    Example:
        def test_get_artists(mock_repository_factory_callable):
            from auralis.player.queue_controller import QueueController
            controller = QueueController(mock_repository_factory_callable)
            # controller now has access to mocked repositories
    """
    def _get_factory():
        """Get mock repository factory instance."""
        return mock_repository_factory

    return _get_factory


@pytest.fixture(params=["library_manager", "repository_factory"])
def mock_data_source(request, mock_library_manager, mock_repository_factory):
    """
    Parametrized fixture for dual-mode backend testing.

    Automatically provides both LibraryManager and RepositoryFactory mocks,
    allowing router tests to validate both access patterns work correctly.

    Phase 5C: Enables automatic dual-mode validation of all router endpoints.

    Example:
        def test_get_artists_both_modes(client, mock_data_source):
            # Test automatically runs with both patterns
            mode, source = mock_data_source
            # Can check which mode and handle accordingly
    """
    if request.param == "library_manager":
        return ("library_manager", mock_library_manager)
    else:
        return ("repository_factory", mock_repository_factory)


@pytest.fixture
def mock_track_repository():
    """Get mock TrackRepository for testing."""
    from unittest.mock import Mock
    repo = Mock()
    repo.get_all = Mock(return_value=([], 0))
    repo.get_by_id = Mock(return_value=None)
    repo.search = Mock(return_value=([], 0))
    repo.create = Mock(return_value=Mock(id=1))
    repo.update = Mock(return_value=Mock(id=1))
    repo.delete = Mock(return_value=True)
    return repo


@pytest.fixture
def mock_album_repository():
    """Get mock AlbumRepository for testing."""
    from unittest.mock import Mock
    repo = Mock()
    repo.get_all = Mock(return_value=([], 0))
    repo.get_by_id = Mock(return_value=None)
    repo.search = Mock(return_value=([], 0))
    repo.create = Mock(return_value=Mock(id=1))
    repo.update = Mock(return_value=Mock(id=1))
    repo.delete = Mock(return_value=True)
    return repo


@pytest.fixture
def mock_artist_repository():
    """Get mock ArtistRepository for testing."""
    from unittest.mock import Mock
    repo = Mock()
    repo.get_all = Mock(return_value=([], 0))
    repo.get_by_id = Mock(return_value=None)
    repo.search = Mock(return_value=([], 0))
    repo.create = Mock(return_value=Mock(id=1))
    repo.update = Mock(return_value=Mock(id=1))
    repo.delete = Mock(return_value=True)
    return repo


# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest with asyncio settings"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
    config.addinivalue_line(
        "markers", "phase5c: Phase 5C dual-mode backend tests"
    )
