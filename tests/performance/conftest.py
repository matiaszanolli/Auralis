"""
Performance Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures and utilities for performance testing.
"""

import pytest
import sys
import time
import tempfile
import os
import shutil
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.library.models import Base
from auralis.io.saver import save


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
