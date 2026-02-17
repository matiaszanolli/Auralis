"""
Auralis Database Migration System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles database schema versioning and migrations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import platform
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.models import Base, SchemaVersion

# Import platform-specific file locking
if platform.system() == "Windows":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)


@contextmanager
def migration_lock(db_path: str, timeout: float = 30.0):
    """
    Acquire an inter-process lock for database migration.

    Uses platform-specific file locking to prevent concurrent migrations.

    Args:
        db_path: Path to database file
        timeout: Maximum time to wait for lock in seconds

    Yields:
        None (lock is held during context)

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        OSError: If lock file cannot be created
    """
    db_path_obj = Path(db_path)
    lock_file = db_path_obj.parent / f".{db_path_obj.name}.migration.lock"

    # Ensure directory exists
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    lock_fd = None
    try:
        # Open lock file
        lock_fd = open(lock_file, 'w')

        if platform.system() == "Windows":
            # Windows: Use msvcrt.locking with retry loop
            import time
            start_time = time.time()
            while True:
                try:
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.time() - start_time >= timeout:
                        raise TimeoutError(
                            f"Could not acquire migration lock within {timeout}s. "
                            "Another process may be migrating the database."
                        )
                    time.sleep(0.1)
        else:
            # Linux/macOS: Use fcntl.flock with timeout
            import time
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.time() - start_time >= timeout:
                        raise TimeoutError(
                            f"Could not acquire migration lock within {timeout}s. "
                            "Another process may be migrating the database."
                        )
                    time.sleep(0.1)

        logger.debug(f"Acquired migration lock: {lock_file}")
        yield

    finally:
        # Release lock and clean up
        if lock_fd:
            try:
                if platform.system() == "Windows":
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                logger.debug(f"Released migration lock: {lock_file}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")

            # Clean up lock file
            try:
                if lock_file.exists():
                    lock_file.unlink()
            except Exception as e:
                logger.warning(f"Could not remove lock file {lock_file}: {e}")


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_path: str):
        """
        Initialize migration manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            connect_args={
                'timeout': 15,          # 15s busy timeout matches LibraryManager
                'check_same_thread': False,
            },
        )

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.migrations_dir = Path(__file__).parent / "migrations"

    def get_current_version(self) -> int:
        """
        Get current database schema version.

        Returns:
            Current schema version number, or 0 if no version table exists
        """
        try:
            # Try to query the schema_version table
            result = self.session.query(SchemaVersion).order_by(
                SchemaVersion.version.desc()
            ).first()

            if result:
                return int(result.version)
            else:
                # Table exists but is empty - this is a fresh database
                return 0
        except Exception as e:
            # Table doesn't exist yet
            logger.debug(f"Schema version table not found: {e}")
            return 0

    def _record_migration(self, version: int, description: str, migration_script: str = "") -> None:
        """
        Record a migration in the schema_version table.

        Args:
            version: Schema version number
            description: Description of the migration
            migration_script: Name of the migration script file
        """
        schema_version = SchemaVersion(
            version=version,
            description=description,
            migration_script=migration_script
        )
        self.session.add(schema_version)
        self.session.commit()
        logger.info(f"✅ Recorded migration to v{version}: {description}")

    def apply_migration(self, from_version: int, to_version: int) -> bool:
        """
        Apply migration from one version to another.

        Args:
            from_version: Current version
            to_version: Target version

        Returns:
            True if successful, False otherwise
        """
        migration_file = f"migration_v{from_version:03d}_to_v{to_version:03d}.sql"
        migration_path = self.migrations_dir / migration_file

        if not migration_path.exists():
            logger.error(f"Migration script not found: {migration_file}")
            return False

        logger.info(f"Applying migration: {migration_file}")

        try:
            # Read migration SQL
            with open(migration_path) as f:
                sql = f.read()

            # Execute migration in a transaction
            with self.engine.begin() as conn:
                # Split by semicolons and execute each statement
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                for statement in statements:
                    if statement:
                        conn.execute(text(statement))

            # Record the migration
            self._record_migration(
                to_version,
                f"Migrated from v{from_version} to v{to_version}",
                migration_file
            )

            logger.info(f"✅ Migration to v{to_version} completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            self.session.rollback()
            raise

    def initialize_fresh_database(self) -> bool:
        """
        Initialize a fresh database with current schema.

        Returns:
            True if successful
        """
        logger.info("Initializing fresh database...")

        try:
            # Create all tables
            Base.metadata.create_all(self.engine)

            # Record initial schema version
            self._record_migration(
                __db_schema_version__,
                "Initial schema",
                "initial"
            )

            logger.info(f"✅ Fresh database initialized with schema v{__db_schema_version__}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise

    def migrate_to_latest(self) -> bool:
        """
        Migrate database to the latest schema version.

        Returns:
            True if successful or already up-to-date
        """
        current_version = self.get_current_version()
        target_version = __db_schema_version__

        if current_version == target_version:
            logger.info(f"Database is already at latest version (v{current_version})")
            return True

        if current_version > target_version:
            logger.error(
                f"Database version (v{current_version}) is newer than "
                f"application version (v{target_version}). "
                f"Please upgrade the application."
            )
            return False

        # Fresh database - no version table
        if current_version == 0:
            return self.initialize_fresh_database()

        # Apply migrations step by step
        logger.info(f"Migrating database from v{current_version} to v{target_version}")

        while current_version < target_version:
            next_version = current_version + 1
            logger.info(f"Migrating to v{next_version}...")

            if not self.apply_migration(current_version, next_version):
                logger.error(f"Migration to v{next_version} failed")
                return False

            current_version = next_version

        logger.info(f"✅ Database successfully migrated to v{target_version}")
        return True

    def close(self) -> None:
        """Close database connection."""
        self.session.close()


def backup_database(db_path: str, backup_dir: str | None = None) -> str:
    """
    Create a backup of the database file.

    Args:
        db_path: Path to database file
        backup_dir: Optional directory for backups (defaults to same dir as db)

    Returns:
        Path to the backup file
    """
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # Determine backup directory
    if backup_dir:
        backup_path = Path(backup_dir)
    else:
        backup_path = db_path_obj.parent

    backup_path.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"{db_path_obj.stem}.backup_{timestamp}{db_path_obj.suffix}"

    # Copy database file
    shutil.copy2(db_path_obj, backup_file)

    logger.info(f"✅ Database backed up to: {backup_file}")
    return str(backup_file)


def restore_database(backup_path: str, db_path: str) -> bool:
    """
    Restore database from backup.

    Args:
        backup_path: Path to backup file
        db_path: Path to database file to restore

    Returns:
        True if successful
    """
    backup_path_obj = Path(backup_path)
    db_path_obj = Path(db_path)

    if not backup_path_obj.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    try:
        # Copy backup over current database
        shutil.copy2(backup_path_obj, db_path_obj)
        logger.info(f"✅ Database restored from: {backup_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to restore database: {e}")
        return False


def check_and_migrate_database(db_path: str, auto_backup: bool = True) -> bool:
    """
    Check database version and migrate if needed.

    Uses inter-process file locking to prevent concurrent migrations.

    Args:
        db_path: Path to database file
        auto_backup: Whether to automatically backup before migration

    Returns:
        True if database is ready (already up-to-date or successfully migrated)

    Raises:
        TimeoutError: If migration lock cannot be acquired
    """
    manager = MigrationManager(db_path)

    try:
        current_version = manager.get_current_version()
        target_version = __db_schema_version__

        # Already up-to-date - no lock needed
        if current_version == target_version:
            logger.info(f"Database is up-to-date (v{current_version})")
            return True

        # Version too new
        if current_version > target_version:
            logger.error(
                f"Database version (v{current_version}) is newer than "
                f"application (v{target_version}). Please upgrade the application."
            )
            return False

        # Migration needed - acquire inter-process lock
        logger.info(f"Database migration needed: v{current_version} → v{target_version}")

        with migration_lock(db_path):
            # Re-check version after acquiring lock (another process may have migrated)
            current_version = manager.get_current_version()
            if current_version == target_version:
                logger.info(f"Database already migrated by another process (v{current_version})")
                return True

            # Backup before migration
            if auto_backup and current_version > 0:
                try:
                    backup_path = backup_database(db_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to create backup: {e}")
                    logger.error("❌ Aborting migration - backup failed")
                    return False

            # Perform migration
            success = manager.migrate_to_latest()

            if success:
                logger.info("✅ Database migration completed successfully")
            else:
                logger.error("❌ Database migration failed")

            return success

    except TimeoutError as e:
        logger.error(f"❌ {e}")
        return False

    except Exception as e:
        logger.error(f"❌ Error during migration check: {e}")
        return False

    finally:
        manager.close()
