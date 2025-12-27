"""
Performance Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures and utilities for performance testing.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.io.saver import save
from auralis.library.models import Base


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    db_path = temp_file.name

    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def get_session():
        return Session()

    yield get_session

    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def performance_audio_file(temp_audio_dir):
    """Create standard test audio file for performance testing."""
    sample_rate = 44100
    duration = 5.0  # 5 seconds
    audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
    filepath = os.path.join(temp_audio_dir, 'perf_test.wav')
    save(filepath, audio, sample_rate, subtype='PCM_16')
    return filepath


@pytest.fixture
def large_audio_file(temp_audio_dir):
    """Create large audio file (3 minutes) for throughput testing."""
    sample_rate = 44100
    duration = 180.0  # 3 minutes
    audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
    filepath = os.path.join(temp_audio_dir, 'large_test.wav')
    save(filepath, audio, sample_rate, subtype='PCM_16')
    return filepath


class Timer:
    """Context manager for measuring execution time."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.elapsed = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time

    @property
    def elapsed_ms(self):
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000 if self.elapsed else None


@pytest.fixture
def timer():
    """Provide timer utility for benchmarking."""
    return Timer


@pytest.fixture
def benchmark_results():
    """Shared dictionary for collecting benchmark results."""
    return {}


# ============================================================================
# Phase 5D: Parametrized Dual-Mode Performance Fixtures
# ============================================================================

@pytest.fixture
def repository_factory_performance():
    """
    Create RepositoryFactory with in-memory database for performance testing.

    Phase 5D: Enables performance comparison between different data access
    patterns using the RepositoryFactory pattern.
    """
    from auralis.library.repositories.factory import RepositoryFactory

    engine = create_engine('sqlite:///:memory:',
                          connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    factory = RepositoryFactory(SessionLocal)
    yield factory

    try:
        engine.dispose()
    except Exception:
        pass


@pytest.fixture
def repository_factory_performance_v2():
    """
    Create second instance of RepositoryFactory for dual-mode testing.

    Phase 5D: Separate instance allows testing same operations against
    different database instances (useful for comparison testing).
    """
    from auralis.library.repositories.factory import RepositoryFactory

    engine = create_engine('sqlite:///:memory:',
                          connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    factory = RepositoryFactory(SessionLocal)
    yield factory

    try:
        engine.dispose()
    except Exception:
        pass


@pytest.fixture(params=["factory_instance1", "factory_instance2"])
def performance_data_source(request, repository_factory_performance, repository_factory_performance_v2):
    """
    Parametrized fixture for dual-mode performance testing.

    Automatically provides two RepositoryFactory instances for performance
    comparison testing and validation.

    Phase 5D: Enables performance tests to validate that patterns meet
    the same benchmark thresholds under identical conditions.

    Example:
        def test_query_performance_both_modes(performance_data_source, timer):
            mode, source = performance_data_source
            # Performance test runs with both factory instances
            with timer() as t:
                tracks, total = source.tracks.get_all(limit=1000)
            # Both instances should meet same performance threshold
            assert t.elapsed < 0.5  # 500ms max
    """
    if request.param == "factory_instance1":
        return ("factory_instance1", repository_factory_performance)
    else:
        return ("factory_instance2", repository_factory_performance_v2)


def create_test_tracks(track_repo, count):
    """Helper to create multiple test tracks."""
    tracks = []
    for i in range(count):
        track = track_repo.add({
            'filepath': f'/tmp/perf_track_{i}.flac',
            'title': f'Performance Track {i}',
            'artists': [f'Artist {i % 10}'],
            'album': f'Album {i % 5}',
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2,
            'play_count': i % 100
        })
        tracks.append(track)
    return tracks


@pytest.fixture
def populated_db(temp_db):
    """Database with 1000 tracks for performance testing."""
    from auralis.library.repositories import TrackRepository
    track_repo = TrackRepository(temp_db)
    create_test_tracks(track_repo, 1000)
    yield temp_db


@pytest.fixture
def populated_repository_factory():
    """
    Create populated RepositoryFactory with 1000 test tracks.

    Phase 5D: Enables performance comparison for repository operations.
    """
    from auralis.library.repositories.factory import RepositoryFactory

    engine = create_engine('sqlite:///:memory:',
                          connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    factory = RepositoryFactory(SessionLocal)

    # Populate with 1000 test tracks
    create_test_tracks(factory.tracks, 1000)

    yield factory

    try:
        engine.dispose()
    except Exception:
        pass


@pytest.fixture
def populated_repository_factory_v2():
    """
    Create second populated RepositoryFactory instance for dual-mode testing.

    Phase 5D: Separate instance allows comparing performance across instances.
    """
    from auralis.library.repositories.factory import RepositoryFactory

    engine = create_engine('sqlite:///:memory:',
                          connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    factory = RepositoryFactory(SessionLocal)

    # Populate with 1000 test tracks
    create_test_tracks(factory.tracks, 1000)

    yield factory

    try:
        engine.dispose()
    except Exception:
        pass


@pytest.fixture(params=["factory_instance1", "factory_instance2"])
def populated_data_source(request, populated_repository_factory, populated_repository_factory_v2):
    """
    Parametrized fixture providing populated RepositoryFactory instances.

    Phase 5D: Automatically provides two instances for dual-mode performance testing.
    Runs tests twice - once with each instance.

    Example:
        def test_latency(populated_data_source, timer):
            mode, source = populated_data_source
            # Performance test runs with both factory instances
            with timer() as t:
                tracks, total = source.tracks.get_all(limit=100)
            assert t.elapsed < 0.1
    """
    if request.param == "factory_instance1":
        return ("factory_instance1", populated_repository_factory)
    else:
        return ("factory_instance2", populated_repository_factory_v2)
