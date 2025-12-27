# -*- coding: utf-8 -*-

"""
Concurrency Test Fixtures
~~~~~~~~~~~~~~~~~~~~~~~~~

Shared fixtures for concurrency testing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import multiprocessing
import shutil
import tempfile
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from queue import Queue

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def thread_pool():
    """Thread pool for concurrent execution."""
    pool = ThreadPoolExecutor(max_workers=10)
    yield pool
    pool.shutdown(wait=True)


@pytest.fixture
def small_thread_pool():
    """Small thread pool (4 workers) for testing."""
    pool = ThreadPoolExecutor(max_workers=4)
    yield pool
    pool.shutdown(wait=True)


@pytest.fixture
def process_pool():
    """Process pool for parallel execution."""
    pool = ProcessPoolExecutor(max_workers=4)
    yield pool
    pool.shutdown(wait=True)


@pytest.fixture
def barrier():
    """Barrier for synchronizing 10 threads."""
    return threading.Barrier(10)


@pytest.fixture
def small_barrier():
    """Barrier for synchronizing 4 threads."""
    return threading.Barrier(4)


@pytest.fixture
def lock():
    """Lock for protecting shared resources."""
    return threading.Lock()


@pytest.fixture
def rlock():
    """Reentrant lock for nested locking."""
    return threading.RLock()


@pytest.fixture
def event():
    """Event for thread signaling."""
    return threading.Event()


@pytest.fixture
def queue():
    """Thread-safe queue."""
    return Queue()


@pytest.fixture
def semaphore():
    """Semaphore for limiting concurrent access."""
    return threading.Semaphore(5)


@pytest.fixture
def condition():
    """Condition variable for thread coordination."""
    return threading.Condition()


@pytest.fixture
def test_audio_files(tmp_path):
    """Create multiple test audio files for concurrent processing."""
    files = []
    for i in range(10):
        # Create 1 second of random audio
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
        filepath = tmp_path / f"test_{i}.wav"
        sf.write(str(filepath), audio, 44100)
        files.append(str(filepath))

    return files


@pytest.fixture
def large_test_audio_files(tmp_path):
    """Create larger test audio files (5 seconds each)."""
    files = []
    for i in range(5):
        # Create 5 seconds of random audio
        audio = np.random.randn(44100 * 5, 2).astype(np.float32) * 0.1
        filepath = tmp_path / f"large_test_{i}.wav"
        sf.write(str(filepath), audio, 44100)
        files.append(str(filepath))

    return files


@pytest.fixture
def temp_audio_dir(tmp_path):
    """Create a temporary directory with audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    # Create some test audio files
    for i in range(20):
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
        filepath = audio_dir / f"track_{i:02d}.wav"
        sf.write(str(filepath), audio, 44100)

    yield str(audio_dir)

    # Cleanup
    if audio_dir.exists():
        shutil.rmtree(audio_dir)


@pytest.fixture
def shared_counter():
    """Thread-safe counter for testing race conditions."""
    class Counter:
        def __init__(self):
            self.value = 0
            self.lock = threading.Lock()

        def increment(self):
            with self.lock:
                self.value += 1

        def increment_unsafe(self):
            """Unsafe increment for demonstrating race conditions."""
            temp = self.value
            # Simulate some work
            import time
            time.sleep(0.0001)
            self.value = temp + 1

        def get(self):
            with self.lock:
                return self.value

    return Counter()


@pytest.fixture
def shared_list():
    """Thread-safe list for testing."""
    class SafeList:
        def __init__(self):
            self.items = []
            self.lock = threading.Lock()

        def append(self, item):
            with self.lock:
                self.items.append(item)

        def get_all(self):
            with self.lock:
                return self.items.copy()

        def __len__(self):
            with self.lock:
                return len(self.items)

    return SafeList()


@pytest.fixture
def temp_db():
    """In-memory SQLite database for concurrent testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Base

    # Create in-memory database
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)

    # Create session factory
    Session = sessionmaker(bind=engine)

    yield Session

    # Cleanup
    engine.dispose()


@pytest.fixture
def concurrent_test_timeout():
    """Timeout for concurrent tests (30 seconds)."""
    return 30


@pytest.fixture(autouse=True)
def cleanup_threads():
    """Ensure all threads are cleaned up after each test."""
    yield

    # Wait for all non-daemon threads to finish
    import time
    main_thread = threading.main_thread()
    for thread in threading.enumerate():
        if thread is not main_thread and not thread.daemon and thread.is_alive():
            thread.join(timeout=5)
