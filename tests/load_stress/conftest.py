"""
Load/Stress Test Fixtures
~~~~~~~~~~~~~~~~~~~~~~~~~

Shared fixtures for load and stress testing.
"""

import pytest
import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from auralis.library.models import Base


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    db_url = f'sqlite:///{db_path}'

    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))

    yield Session

    Session.remove()
    engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_audio_file(temp_audio_dir):
    """Create a test audio file."""
    import soundfile as sf

    # 1 second of test audio
    audio = np.random.randn(44100) * 0.1
    filepath = os.path.join(temp_audio_dir, 'test_audio.wav')
    sf.write(filepath, audio, 44100, subtype='PCM_16')

    return filepath


@pytest.fixture
def long_audio_file(temp_audio_dir):
    """Create a long test audio file (5 minutes)."""
    import soundfile as sf

    # 5 minutes of test audio
    duration = 5 * 60  # 5 minutes
    audio = np.random.randn(44100 * duration) * 0.1
    filepath = os.path.join(temp_audio_dir, 'long_audio.wav')
    sf.write(filepath, audio, 44100, subtype='PCM_16')

    return filepath


@pytest.fixture
def large_track_dataset(temp_db):
    """
    Create large dataset of tracks for load testing.

    Returns function that generates N tracks.
    """
    from auralis.library.repositories import TrackRepository, AlbumRepository
    from auralis.library.models import Artist, Album

    def _create_tracks(count: int):
        """Create N tracks in database."""
        track_repo = TrackRepository(temp_db)
        session = temp_db()

        # Create artists
        artists = []
        for i in range(min(count // 10, 100)):  # Max 100 artists
            artist = Artist(name=f'Artist {i}')
            session.add(artist)
            artists.append(artist)
        session.commit()

        # Create albums
        albums = []
        for i in range(min(count // 5, 200)):  # Max 200 albums
            album = Album(
                title=f'Album {i}',
                artist_id=artists[i % len(artists)].id,
                year=2000 + (i % 25)
            )
            session.add(album)
            albums.append(album)
        session.commit()

        # Pre-extract names to avoid lazy loading issues
        artist_names = [a.name for a in artists]
        album_titles = [a.title for a in albums]
        session.close()

        # Create tracks
        created_tracks = []
        for i in range(count):
            track_info = {
                'filepath': f'/tmp/load_test_track_{i}.flac',
                'title': f'Load Test Track {i}',
                'artists': [artist_names[i % len(artist_names)]],
                'album': album_titles[i % len(album_titles)],
                'year': 2000 + (i % 25),
                'track_number': (i % 20) + 1,
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2,
                'duration': 180.0 + (i % 300),  # 3-8 minutes
            }
            track = track_repo.add(track_info)
            created_tracks.append(track)

        return created_tracks

    return _create_tracks


@pytest.fixture
def resource_monitor():
    """
    Monitor system resources during test execution.

    Returns a context manager that tracks CPU, memory, and time.
    """
    import psutil
    import time

    class ResourceMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.start_time = None
            self.start_memory = None
            self.start_cpu_percent = None
            self.peak_memory = 0

        def __enter__(self):
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.start_cpu_percent = self.process.cpu_percent()
            self.peak_memory = self.start_memory
            return self

        def __exit__(self, *args):
            pass

        def update(self):
            """Update peak memory usage."""
            current_memory = self.process.memory_info().rss / 1024 / 1024
            self.peak_memory = max(self.peak_memory, current_memory)

        @property
        def elapsed_seconds(self):
            """Get elapsed time in seconds."""
            return time.time() - self.start_time

        @property
        def memory_growth_mb(self):
            """Get memory growth in MB."""
            current_memory = self.process.memory_info().rss / 1024 / 1024
            return current_memory - self.start_memory

        @property
        def peak_memory_mb(self):
            """Get peak memory usage in MB."""
            return self.peak_memory

    return ResourceMonitor


@pytest.fixture
def concurrent_executor():
    """
    Concurrent execution helper for stress testing.

    Returns a function that executes tasks in parallel.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    def _execute_concurrent(tasks, max_workers=10):
        """
        Execute tasks concurrently and return results.

        Args:
            tasks: List of callables to execute
            max_workers: Maximum number of concurrent workers

        Returns:
            List of (success, result_or_error) tuples
        """
        results = []
        errors = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(task) for task in tasks]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append((True, result))
                except Exception as e:
                    results.append((False, e))
                    errors.append(e)

        return results, errors

    return _execute_concurrent


@pytest.fixture
def load_test_config():
    """
    Configuration for load tests.

    Adjust these values based on test environment.
    """
    return {
        # Library size targets
        'small_library': 1000,      # 1k tracks
        'medium_library': 10000,    # 10k tracks
        'large_library': 50000,     # 50k tracks
        'huge_library': 100000,     # 100k tracks (stress test)

        # Concurrency levels
        'low_concurrency': 10,      # 10 parallel operations
        'medium_concurrency': 50,   # 50 parallel operations
        'high_concurrency': 100,    # 100 parallel operations
        'extreme_concurrency': 500, # 500 parallel operations

        # Time limits
        'quick_test_seconds': 5,
        'medium_test_seconds': 30,
        'long_test_seconds': 300,   # 5 minutes

        # Resource limits
        'max_memory_growth_mb': 500,  # Max 500MB growth
        'max_memory_percent': 50,     # Max 50% system memory
        'max_cpu_percent': 90,        # Max 90% CPU

        # Performance targets
        'min_queries_per_second': 1000,
        'max_query_latency_ms': 100,
        'min_real_time_factor': 10,  # 10x real-time processing
    }
