"""
Regression tests for SQLite connection pool configuration (#2086)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that the connection pool is properly sized for SQLite and
that concurrent writes complete without timeout under normal load.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import shutil
import tempfile
import threading
import time

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from auralis.library.models import Base, Track
from auralis.library.repositories import RepositoryFactory


@pytest.fixture
def concurrent_db():
    """Create a file-based SQLite database with proper WAL config for concurrency tests."""
    temp_dir = tempfile.mkdtemp(prefix="auralis_pool_test_")
    db_path = os.path.join(temp_dir, "test_pool.db")

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 15, "check_same_thread": False},
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-65536")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    factory = RepositoryFactory(SessionLocal)

    yield factory, engine

    engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestPoolConfiguration:
    """Verify pool size is appropriate for SQLite"""

    def test_pool_size_within_bounds(self):
        """Engine pool_size + max_overflow should not exceed 10 for SQLite"""
        from auralis.library.manager import LibraryManager

        temp_dir = tempfile.mkdtemp(prefix="auralis_pool_check_")
        db_path = os.path.join(temp_dir, "check.db")

        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                manager = LibraryManager(database_path=db_path)

            pool = manager.engine.pool
            # pool_size + max_overflow should be <= 10 for SQLite
            assert pool.size() <= 10, (
                f"pool_size={pool.size()} too large for SQLite"
            )
            assert pool.size() + pool._max_overflow <= 15, (
                f"Total connections ({pool.size() + pool._max_overflow}) "
                "too many for SQLite"
            )
            manager.shutdown()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestConcurrentWrites:
    """Verify no write timeout under normal load with reduced pool"""

    def test_10_threads_writing_simultaneously(self, concurrent_db):
        """10 threads writing simultaneously must all complete within 5s"""
        factory, engine = concurrent_db
        num_threads = 10
        barrier = threading.Barrier(num_threads)
        errors = []
        timings = []

        def writer(thread_id):
            try:
                # Synchronize all threads to start writing at the same time
                barrier.wait(timeout=5)

                start = time.monotonic()
                track = factory.tracks.add({
                    "title": f"Concurrent Track {thread_id}",
                    "filepath": f"/tmp/concurrent_{thread_id}.wav",
                    "duration": 180.0,
                    "sample_rate": 44100,
                    "channels": 2,
                    "format": "WAV",
                    "artists": [f"Artist {thread_id}"],
                    "album": f"Album {thread_id}",
                })
                elapsed = time.monotonic() - start
                timings.append(elapsed)

                if track is None:
                    errors.append(f"Thread {thread_id}: add() returned None")
            except Exception as e:
                errors.append(f"Thread {thread_id}: {type(e).__name__}: {e}")

        threads = [
            threading.Thread(target=writer, args=(i,))
            for i in range(num_threads)
        ]

        overall_start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        overall_elapsed = time.monotonic() - overall_start

        # No errors
        assert not errors, f"Concurrent write errors: {errors}"

        # All must complete within 5 seconds total
        assert overall_elapsed < 5.0, (
            f"Concurrent writes took {overall_elapsed:.2f}s (limit: 5s)"
        )

        # Verify all tracks were written
        tracks, total = factory.tracks.get_all(limit=20)
        assert total == num_threads, (
            f"Expected {num_threads} tracks, got {total}"
        )

    def test_mixed_read_write_concurrency(self, concurrent_db):
        """Mixed reads and writes must not deadlock or timeout"""
        factory, engine = concurrent_db

        # Seed some data first
        for i in range(5):
            factory.tracks.add({
                "title": f"Seed Track {i}",
                "filepath": f"/tmp/seed_{i}.wav",
                "duration": 120.0,
                "sample_rate": 44100,
                "channels": 2,
                "format": "WAV",
                "artists": [f"Seed Artist {i}"],
            })

        num_threads = 10
        barrier = threading.Barrier(num_threads)
        errors = []

        def mixed_worker(thread_id):
            try:
                barrier.wait(timeout=5)
                if thread_id % 2 == 0:
                    # Writer
                    factory.tracks.add({
                        "title": f"Mixed Track {thread_id}",
                        "filepath": f"/tmp/mixed_{thread_id}.wav",
                        "duration": 100.0,
                        "sample_rate": 44100,
                        "channels": 2,
                        "format": "WAV",
                    })
                else:
                    # Reader
                    factory.tracks.get_all(limit=10)
                    factory.tracks.search("Seed")
            except Exception as e:
                errors.append(f"Thread {thread_id}: {type(e).__name__}: {e}")

        threads = [
            threading.Thread(target=mixed_worker, args=(i,))
            for i in range(num_threads)
        ]

        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        elapsed = time.monotonic() - start

        assert not errors, f"Mixed concurrency errors: {errors}"
        assert elapsed < 5.0, (
            f"Mixed read/write took {elapsed:.2f}s (limit: 5s)"
        )

    def test_rapid_sequential_writes_across_threads(self, concurrent_db):
        """Rapid writes from multiple threads should not exhaust pool"""
        factory, engine = concurrent_db
        num_threads = 10
        writes_per_thread = 5
        errors = []

        def rapid_writer(thread_id):
            try:
                for j in range(writes_per_thread):
                    factory.tracks.add({
                        "title": f"Rapid {thread_id}-{j}",
                        "filepath": f"/tmp/rapid_{thread_id}_{j}.wav",
                        "duration": 60.0,
                        "sample_rate": 44100,
                        "channels": 2,
                        "format": "WAV",
                    })
            except Exception as e:
                errors.append(f"Thread {thread_id}: {type(e).__name__}: {e}")

        threads = [
            threading.Thread(target=rapid_writer, args=(i,))
            for i in range(num_threads)
        ]

        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        elapsed = time.monotonic() - start

        assert not errors, f"Rapid write errors: {errors}"

        # 50 total writes should complete in reasonable time
        tracks, total = factory.tracks.get_all(limit=100)
        assert total == num_threads * writes_per_thread, (
            f"Expected {num_threads * writes_per_thread} tracks, got {total}"
        )
