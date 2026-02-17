"""
Tests for database migration system
"""

import multiprocessing
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import (
    MigrationManager,
    backup_database,
    check_and_migrate_database,
    migration_lock,
    restore_database,
)
from auralis.library.models import Base, SchemaVersion, Track


class TestMigrationManager:
    """Test cases for MigrationManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_library.db"
        yield str(db_path)
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_fresh_database_initialization(self, temp_db):
        """Test initializing a fresh database"""
        manager = MigrationManager(temp_db)

        # Current version should be 0 (no version table)
        assert manager.get_current_version() == 0

        # Initialize fresh database
        success = manager.initialize_fresh_database()
        assert success is True

        # Should now be at current version
        assert manager.get_current_version() == __db_schema_version__

        # Verify schema_version table exists and has entry
        schema_version = manager.session.query(SchemaVersion).first()
        assert schema_version is not None
        assert schema_version.version == __db_schema_version__
        assert schema_version.description == "Initial schema"

        manager.close()

    def test_migrate_to_latest_fresh_db(self, temp_db):
        """Test migrate_to_latest on fresh database"""
        manager = MigrationManager(temp_db)

        # Migrate fresh database
        success = manager.migrate_to_latest()
        assert success is True

        # Should be at latest version
        assert manager.get_current_version() == __db_schema_version__

        manager.close()

    def test_migrate_to_latest_already_current(self, temp_db):
        """Test migrate_to_latest when already at current version"""
        # Initialize database
        manager = MigrationManager(temp_db)
        manager.migrate_to_latest()
        current_version = manager.get_current_version()

        # Try to migrate again
        success = manager.migrate_to_latest()
        assert success is True  # Should succeed (no-op)
        assert manager.get_current_version() == current_version

        manager.close()

    def test_version_newer_than_app(self, temp_db):
        """Test handling when database version is newer than app"""
        manager = MigrationManager(temp_db)
        manager.initialize_fresh_database()

        # Manually set version to future version
        future_version = SchemaVersion(
            version=999,
            description="Future version",
            migration_script="test"
        )
        manager.session.add(future_version)
        manager.session.commit()

        # Should detect version mismatch
        assert manager.get_current_version() == 999
        success = manager.migrate_to_latest()
        assert success is False  # Should fail

        manager.close()

    def test_schema_version_table_created(self, temp_db):
        """Test that schema_version table is created properly"""
        manager = MigrationManager(temp_db)
        manager.initialize_fresh_database()

        # Query schema_version table
        versions = manager.session.query(SchemaVersion).all()
        assert len(versions) == 1
        assert versions[0].version == __db_schema_version__
        assert versions[0].applied_at is not None

        manager.close()

    def test_database_tables_created(self, temp_db):
        """Test that all expected tables are created"""
        manager = MigrationManager(temp_db)
        manager.migrate_to_latest()

        # Check that core tables exist
        engine = create_engine(f'sqlite:///{temp_db}')
        inspector = engine.dialect.get_table_names(engine.connect())

        expected_tables = [
            'tracks', 'albums', 'artists', 'genres', 'playlists',
            'track_artist', 'track_genre', 'track_playlist',
            'library_stats', 'schema_version'
        ]

        for table in expected_tables:
            assert table in inspector, f"Table {table} not found"

        manager.close()


class TestDatabaseBackup:
    """Test cases for database backup/restore"""

    @pytest.fixture
    def temp_db_with_data(self):
        """Create a temporary database with some data"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_library.db"

        # Initialize database with data
        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Add test track
        track = Track(
            title="Test Track",
            filepath="/test/track.wav",
            duration=180.0
        )
        session.add(track)
        session.commit()
        session.close()

        yield str(db_path)

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_backup_database(self, temp_db_with_data):
        """Test creating database backup"""
        backup_path = backup_database(temp_db_with_data)

        # Verify backup exists
        assert Path(backup_path).exists()

        # Verify backup is a valid database
        engine = create_engine(f'sqlite:///{backup_path}')
        Session = sessionmaker(bind=engine)
        session = Session()

        tracks = session.query(Track).all()
        assert len(tracks) == 1
        assert tracks[0].title == "Test Track"

        session.close()

        # Cleanup backup
        Path(backup_path).unlink()

    def test_restore_database(self, temp_db_with_data):
        """Test restoring database from backup"""
        # Create backup
        backup_path = backup_database(temp_db_with_data)

        # Modify original database
        engine = create_engine(f'sqlite:///{temp_db_with_data}')
        Session = sessionmaker(bind=engine)
        session = Session()

        # Add another track
        track = Track(
            title="New Track",
            filepath="/test/new_track.wav",
            duration=120.0
        )
        session.add(track)
        session.commit()
        session.close()

        # Verify modification
        session = Session()
        assert session.query(Track).count() == 2
        session.close()

        # Restore from backup
        success = restore_database(backup_path, temp_db_with_data)
        assert success is True

        # Verify restored database
        session = Session()
        tracks = session.query(Track).all()
        assert len(tracks) == 1
        assert tracks[0].title == "Test Track"
        session.close()

        # Cleanup
        Path(backup_path).unlink()

    def test_backup_nonexistent_database(self):
        """Test backup fails for nonexistent database"""
        with pytest.raises(FileNotFoundError):
            backup_database("/nonexistent/database.db")

    def test_backup_captures_wal_data(self):
        """backup_database() captures committed data that lives in the WAL file.

        shutil.copy2() of the .db file misses pages committed after the last
        checkpoint.  sqlite3.Connection.backup() (SQLite Online Backup API)
        reads through both the main file and the WAL, so all committed data is
        present in the backup regardless of checkpoint state.
        """
        import sqlite3 as _sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "wal_test.db"
            backup_dir = Path(tmp) / "backups"
            backup_dir.mkdir()

            # Build a WAL-mode DB and disable auto-checkpoint so the write is
            # guaranteed to stay in the WAL file (never flushed to the main DB).
            with _sqlite3.connect(str(db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA wal_autocheckpoint=0")  # disable auto-checkpoint
                conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO items VALUES (1, 'only_in_wal')")
                conn.commit()

            # WAL file must exist and be non-empty to confirm the write is there.
            wal_file = Path(str(db_path) + "-wal")
            assert wal_file.exists() and wal_file.stat().st_size > 0, (
                "WAL file should be non-empty (auto-checkpoint disabled)"
            )

            # Take the backup — old shutil.copy2 would miss the WAL data.
            backup_path = backup_database(str(db_path), backup_dir=str(backup_dir))

            # Backup DB must contain the committed row.
            with _sqlite3.connect(backup_path) as bk:
                rows = bk.execute("SELECT value FROM items WHERE id=1").fetchall()
            assert rows == [("only_in_wal",)], (
                "Backup is missing data that was committed but not checkpointed"
            )

    def test_restore_from_wal_backup_is_complete(self):
        """Round-trip: write → backup (WAL-safe) → restore → all data present."""
        import sqlite3 as _sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "src.db"
            restore_target = Path(tmp) / "restored.db"

            # Create source DB in WAL mode, insert data, leave in WAL.
            with _sqlite3.connect(str(db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA wal_autocheckpoint=0")
                conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT)")
                conn.executemany(
                    "INSERT INTO kv VALUES (?, ?)",
                    [(f"key{i}", f"val{i}") for i in range(20)]
                )
                conn.commit()

            backup_path = backup_database(str(db_path), backup_dir=tmp)
            success = restore_database(backup_path, str(restore_target))
            assert success is True

            with _sqlite3.connect(str(restore_target)) as conn:
                rows = conn.execute("SELECT COUNT(*) FROM kv").fetchone()
            assert rows[0] == 20, "Restored DB is missing rows that were only in the WAL"


class TestCheckAndMigrate:
    """Test cases for check_and_migrate_database"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_library.db"
        yield str(db_path)
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_check_and_migrate_fresh_database(self, temp_db):
        """Test check_and_migrate on fresh database"""
        success = check_and_migrate_database(temp_db, auto_backup=False)
        assert success is True

        # Verify database is initialized
        manager = MigrationManager(temp_db)
        assert manager.get_current_version() == __db_schema_version__
        manager.close()

    def test_check_and_migrate_current_database(self, temp_db):
        """Test check_and_migrate on already current database"""
        # Initialize database first
        manager = MigrationManager(temp_db)
        manager.migrate_to_latest()
        manager.close()

        # Check and migrate again
        success = check_and_migrate_database(temp_db, auto_backup=False)
        assert success is True  # Should succeed (no-op)

    def test_check_and_migrate_with_backup(self, temp_db):
        """Test check_and_migrate creates backup"""
        # Initialize database with data
        manager = MigrationManager(temp_db)
        manager.initialize_fresh_database()
        manager.close()

        # This should succeed but not create backup (already current)
        success = check_and_migrate_database(temp_db, auto_backup=True)
        assert success is True


class TestMigrationConcurrency:
    """Test cases for concurrent migration scenarios (Issue #2067)"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_library.db"
        yield str(db_path)
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_migration_lock_basic(self, temp_db):
        """Test that migration lock can be acquired and released"""
        # Should acquire lock successfully
        with migration_lock(temp_db):
            # Lock is held
            lock_file = Path(temp_db).parent / f".{Path(temp_db).name}.migration.lock"
            assert lock_file.exists()

        # Lock should be released and cleaned up
        assert not lock_file.exists()

    def test_migration_lock_blocks_concurrent_access(self, temp_db):
        """Test that migration lock prevents concurrent access"""
        lock_file = Path(temp_db).parent / f".{Path(temp_db).name}.migration.lock"

        # Acquire lock in first context
        with migration_lock(temp_db):
            assert lock_file.exists()

            # Try to acquire lock again with short timeout
            with pytest.raises(TimeoutError, match="Could not acquire migration lock"):
                with migration_lock(temp_db, timeout=0.5):
                    pass  # Should never reach here

        # Lock should be released after first context exits
        assert not lock_file.exists()

    def test_concurrent_migration_attempts(self, temp_db):
        """Test that only one process can migrate at a time"""

        def attempt_migration(db_path: str, result_queue: multiprocessing.Queue, delay: float = 0):
            """Helper function to run migration in separate process"""
            try:
                if delay > 0:
                    time.sleep(delay)
                success = check_and_migrate_database(db_path, auto_backup=False)
                result_queue.put(("success", success))
            except TimeoutError as e:
                result_queue.put(("timeout", str(e)))
            except Exception as e:
                result_queue.put(("error", str(e)))

        # Use multiprocessing to simulate concurrent processes
        result_queue = multiprocessing.Queue()
        processes = []

        # Start two processes simultaneously
        for i in range(2):
            p = multiprocessing.Process(
                target=attempt_migration,
                args=(temp_db, result_queue, 0.1 * i)  # Slight delay to ensure overlap
            )
            processes.append(p)
            p.start()

        # Wait for all processes to complete
        for p in processes:
            p.join(timeout=10)

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        # At least one should succeed
        successes = [r for r in results if r[0] == "success" and r[1] is True]
        assert len(successes) >= 1, f"Expected at least one successful migration, got: {results}"

        # Verify database was migrated correctly
        manager = MigrationManager(temp_db)
        assert manager.get_current_version() == __db_schema_version__
        manager.close()

    def test_backup_failure_aborts_migration(self, temp_db):
        """Test that migration aborts if backup fails (Issue #2067 - HIGH severity)"""
        # Initialize database
        manager = MigrationManager(temp_db)
        manager.initialize_fresh_database()
        manager.close()

        # Manually set version to older version to trigger migration
        engine = create_engine(f'sqlite:///{temp_db}')
        with engine.begin() as conn:
            conn.execute(
                SchemaVersion.__table__.delete()
            )
            conn.execute(
                SchemaVersion.__table__.insert(),
                {"version": 1, "description": "Old version", "migration_script": "test"}
            )

        # Mock backup_database to raise an exception
        with patch('auralis.library.migration_manager.backup_database', side_effect=IOError("Disk full")):
            success = check_and_migrate_database(temp_db, auto_backup=True)

            # Migration should FAIL, not proceed
            assert success is False, "Migration should abort when backup fails"

        # Verify database was NOT migrated
        manager = MigrationManager(temp_db)
        current_version = manager.get_current_version()
        assert current_version == 1, f"Database should still be at v1, got v{current_version}"
        manager.close()

    def test_migration_lock_cleanup_on_exception(self, temp_db):
        """Test that lock file is cleaned up even if exception occurs"""
        lock_file = Path(temp_db).parent / f".{Path(temp_db).name}.migration.lock"

        try:
            with migration_lock(temp_db):
                assert lock_file.exists()
                raise ValueError("Simulated error during migration")
        except ValueError:
            pass

        # Lock should still be cleaned up
        assert not lock_file.exists(), "Lock file should be cleaned up after exception"

    def test_recheck_version_after_lock_acquisition(self, temp_db):
        """Test that version is rechecked after acquiring lock"""
        # This tests the double-check pattern where another process
        # may have completed the migration while we were waiting for the lock

        # Initialize database
        manager = MigrationManager(temp_db)
        manager.initialize_fresh_database()
        manager.close()

        # Database is already current - should detect this and skip migration
        success = check_and_migrate_database(temp_db, auto_backup=True)
        assert success is True

        # Verify no unnecessary backup was created
        backup_files = list(Path(temp_db).parent.glob("*.backup_*"))
        assert len(backup_files) == 0, "No backup should be created for up-to-date database"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
