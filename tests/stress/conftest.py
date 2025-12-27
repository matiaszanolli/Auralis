# -*- coding: utf-8 -*-

"""
Stress Test Fixtures
~~~~~~~~~~~~~~~~~~~~

Shared fixtures for stress and load testing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import gc
import shutil
import tempfile
from pathlib import Path

import numpy as np
import psutil
import pytest
import soundfile as sf


@pytest.fixture
def memory_monitor():
    """
    Monitor memory usage during test.

    Yields process object, then checks for memory leaks.
    """
    import os
    process = psutil.Process(os.getpid())
    gc.collect()

    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    yield process

    gc.collect()
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    # Warn if memory increased significantly
    if memory_increase > 500:
        import warnings
        warnings.warn(f"Potential memory leak: {memory_increase:.1f}MB increase")


@pytest.fixture
def cpu_monitor():
    """
    Monitor CPU usage during test.

    Returns dict with before/after CPU percentages.
    """
    cpu_before = psutil.cpu_percent(interval=0.1)

    class CPUMonitor:
        def __init__(self):
            self.cpu_before = cpu_before
            self.cpu_after = None

        def finish(self):
            self.cpu_after = psutil.cpu_percent(interval=0.1)
            return {
                'before': self.cpu_before,
                'after': self.cpu_after,
                'increase': self.cpu_after - self.cpu_before
            }

    monitor = CPUMonitor()
    yield monitor
    monitor.finish()


@pytest.fixture
def large_library_db(tmp_path):
    """
    Create database with 1,000 test tracks.

    Yields sessionmaker that can be called to create new sessions.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Album, Artist, Base, Track

    db_path = tmp_path / "large_library.db"
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)

    # Create initial data in a separate session
    setup_session = Session()
    try:
        # Create artists (100)
        artists = []
        for i in range(100):
            artist = Artist(name=f"Artist {i}")
            setup_session.add(artist)
            artists.append(artist)
        setup_session.flush()

        # Create albums (200)
        albums = []
        for i in range(200):
            album = Album(
                title=f"Album {i}",
                artist=artists[i % len(artists)]
            )
            setup_session.add(album)
            albums.append(album)
        setup_session.flush()

        # Create tracks (1,000)
        for i in range(1000):
            album_idx = i % len(albums)
            track = Track(
                filepath=f"/test/track_{i:04d}.mp3",
                title=f"Track {i:04d}",
                duration=180.0 + (i % 300),  # 3-8 minutes
                album_id=albums[album_idx].id,
                track_number=(i % 20) + 1,
                year=2000 + (i % 25)
            )
            setup_session.add(track)

        setup_session.commit()
    finally:
        setup_session.close()

    # Yield the sessionmaker so tests can create their own sessions
    yield Session

    # Cleanup
    engine.dispose()


@pytest.fixture
def very_large_library_db(tmp_path):
    """
    Create database with 10,000 test tracks (slower).

    Yields sessionmaker that can be called to create new sessions.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Album, Artist, Base, Track

    db_path = tmp_path / "very_large_library.db"
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)

    # Create initial data in a separate session
    setup_session = Session()
    try:
        # Create artists (500)
        artists = []
        for i in range(500):
            artist = Artist(name=f"Artist {i}")
            setup_session.add(artist)
            artists.append(artist)
        setup_session.flush()

        # Create albums (2000)
        albums = []
        for i in range(2000):
            album = Album(
                title=f"Album {i}",
                artist=artists[i % len(artists)]
            )
            setup_session.add(album)
            albums.append(album)
        setup_session.flush()

        # Create tracks (10,000) - commit in batches to avoid memory issues
        batch_size = 1000
        for batch_start in range(0, 10000, batch_size):
            for i in range(batch_start, min(batch_start + batch_size, 10000)):
                album_idx = i % len(albums)
                track = Track(
                    filepath=f"/test/track_{i:05d}.mp3",
                    title=f"Track {i:05d}",
                    duration=180.0 + (i % 300),
                    album_id=albums[album_idx].id,
                    track_number=(i % 20) + 1,
                    year=2000 + (i % 25)
                )
                setup_session.add(track)

            setup_session.commit()
    finally:
        setup_session.close()

    # Yield the sessionmaker so tests can create their own sessions
    yield Session

    # Cleanup
    engine.dispose()


@pytest.fixture
def test_audio_dir(tmp_path):
    """
    Create directory with 100 small test audio files.

    Returns path to directory.
    """
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    for i in range(100):
        # Create 1 second of random audio
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
        filepath = audio_dir / f"track_{i:03d}.wav"
        sf.write(str(filepath), audio, 44100)

    yield str(audio_dir)

    # Cleanup
    if audio_dir.exists():
        shutil.rmtree(audio_dir)


@pytest.fixture
def very_long_audio(tmp_path):
    """
    Create 10-minute test audio file (reduced from 1 hour to prevent memory issues).

    Returns path to audio file.
    """
    filepath = tmp_path / "long_audio.wav"

    # Create 10 minutes of audio in chunks to avoid memory issues
    duration_samples = 600 * 44100  # 10 minutes (reduced from 1 hour)
    chunk_size = 44100 * 10  # 10 second chunks
    num_chunks = duration_samples // chunk_size

    with sf.SoundFile(str(filepath), 'w', 44100, 2, 'PCM_16') as f:
        for _ in range(num_chunks):
            chunk = np.random.randn(chunk_size, 2).astype(np.float32) * 0.1
            f.write(chunk)

    yield str(filepath)


@pytest.fixture
def high_sample_rate_audio(tmp_path):
    """
    Create 192kHz test audio file (10 seconds).

    Returns path to audio file.
    """
    filepath = tmp_path / "high_sr_audio.wav"

    # 10 seconds at 192kHz
    duration_samples = 192000 * 10
    audio = np.random.randn(duration_samples, 2).astype(np.float32) * 0.1

    sf.write(str(filepath), audio, 192000)

    yield str(filepath)


@pytest.fixture
def silent_audio(tmp_path):
    """
    Create completely silent audio file (10 seconds).

    Returns path to audio file.
    """
    filepath = tmp_path / "silent_audio.wav"

    # 10 seconds of silence
    audio = np.zeros((44100 * 10, 2), dtype=np.float32)

    sf.write(str(filepath), audio, 44100)

    yield str(filepath)


@pytest.fixture
def clipping_audio(tmp_path):
    """
    Create audio with clipping (values > 1.0).

    Returns path to audio file.
    """
    filepath = tmp_path / "clipping_audio.wav"

    # Create audio with peaks at 1.5 (clipping)
    audio = np.random.randn(44100 * 5, 2).astype(np.float32) * 0.5
    audio[::1000] = 1.5  # Add clipping peaks

    sf.write(str(filepath), audio, 44100)

    yield str(filepath)


@pytest.fixture
def corrupted_audio(tmp_path):
    """
    Create corrupted audio file (invalid data).

    Returns path to file.
    """
    filepath = tmp_path / "corrupted.wav"

    # Write invalid data to file
    with open(filepath, 'wb') as f:
        f.write(b'This is not a valid WAV file' * 100)

    yield str(filepath)


@pytest.fixture
def zero_length_audio(tmp_path):
    """
    Create zero-length audio file.

    Returns path to file.
    """
    filepath = tmp_path / "zero_length.wav"

    # Create empty audio (0 samples)
    audio = np.array([], dtype=np.float32).reshape(0, 2)

    try:
        sf.write(str(filepath), audio, 44100)
    except Exception:
        # Some versions of soundfile don't support 0-length
        # Create minimal valid WAV manually
        import struct
        with open(filepath, 'wb') as f:
            # Minimal WAV header
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<HHIIHH', 1, 2, 44100, 176400, 4, 16))
            f.write(b'data')
            f.write(struct.pack('<I', 0))

    yield str(filepath)


@pytest.fixture
def unicode_path_audio(tmp_path):
    """
    Create audio file with Unicode characters in path.

    Returns path to file.
    """
    # Create directory with unicode name
    unicode_dir = tmp_path / "音楽_🎵_Music"
    unicode_dir.mkdir()

    filepath = unicode_dir / "トラック_Track_01.wav"

    # Create simple audio
    audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
    sf.write(str(filepath), audio, 44100)

    yield str(filepath)


@pytest.fixture(scope="session")
def stress_test_timeout():
    """Timeout for stress tests (5 minutes)."""
    return 300


@pytest.fixture(autouse=True)
def stress_test_cleanup():
    """Clean up resources after each stress test."""
    yield

    # Force garbage collection
    gc.collect()

    # Give system time to clean up
    import time
    time.sleep(0.1)
