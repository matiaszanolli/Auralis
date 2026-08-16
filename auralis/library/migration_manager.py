"""
Auralis Database Migration System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles database schema versioning and migrations

The lock, the backup/restore helpers and the per-step SQL execution live in
sibling modules since the #4511 split; they are re-exported below so every
existing import of this module keeps working.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.models import Base, SchemaVersion

from .migration_backup import backup_database, restore_database  # re-exported (#4511)
from .migration_engine import create_migration_engine
from .migration_lock import migration_lock  # re-exported (#4511)
from .migration_steps import run_migration_step

logger = logging.getLogger(__name__)

__all__ = [
    'MigrationManager',
    'check_and_migrate_database',
    'migration_lock',
    'backup_database',
    'restore_database',
]


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_path: str):
        """
        Initialize migration manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.engine = create_migration_engine(self.db_path)
        self._SessionFactory = sessionmaker(self.engine)
        self.migrations_dir = Path(__file__).parent / "migrations"

    @contextmanager
    def _get_session(self):
        """Yield a short-lived session that is always closed."""
        session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_current_version(self) -> int:
        """
        Get current database schema version.

        Returns:
            Current schema version number, or 0 if no version table exists
        """
        try:
            with self._get_session() as session:
                result = session.execute(
                    select(SchemaVersion).order_by(SchemaVersion.version.desc())
                ).scalars().first()

                if result:
                    return int(result.version)
                else:
                    # Table exists but is empty - this is a fresh database
                    return 0
        except Exception as e:
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
        with self._get_session() as session:
            schema_version = SchemaVersion(
                version=version,
                description=description,
                migration_script=migration_script
            )
            session.add(schema_version)
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
        # `datetime.now` is passed rather than imported by migration_steps so
        # this module stays the patch point for the atomicity test (#2905).
        return run_migration_step(
            self.engine,
            self.migrations_dir,
            from_version,
            to_version,
            datetime.now,
        )

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

    def __enter__(self) -> "MigrationManager":
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Dispose engine and release all connections (issue #2395)."""
        self.engine.dispose()


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
    with MigrationManager(db_path) as manager:
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
                        # backup_database() already logs "✅ Database backed
                        # up" at INFO; the path itself stays at DEBUG only
                        # (#4929).
                        backup_path = backup_database(db_path)
                        logger.debug(f"Pre-migration backup location: {backup_path}")
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

    return False  # unreachable, satisfies type checker
