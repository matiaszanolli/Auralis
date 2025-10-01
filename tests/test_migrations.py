"""
Tests for database migration system
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from auralis.library.migrations import (
    MigrationManager,
    backup_database,
    restore_database,
    check_and_migrate_database
)
from auralis.library.models import Base, Track, SchemaVersion
from auralis.__version__ import __db_schema_version__
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
