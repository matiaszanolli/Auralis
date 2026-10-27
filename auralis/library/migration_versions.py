"""
Schema-version bookkeeping for MigrationManager (split from
migration_manager.py, #5837): a short-lived session, the current-version read
and the version-row write.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from auralis.library.models import SchemaVersion

logger = logging.getLogger(__name__)

# SQLite's message when the table has never been created.
_MISSING_VERSION_TABLE = "no such table: schema_version"


class SchemaVersionStoreMixin:
    """Reads and writes ``schema_version``; ``_SessionFactory`` is set by MigrationManager."""

    _SessionFactory: sessionmaker[Session]

    @contextmanager
    def _get_session(self) -> Iterator[Session]:
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
            Current schema version number, or 0 for a database with no
            ``schema_version`` table or no row in it (a fresh database).

        Raises:
            sqlalchemy.exc.DatabaseError: any other read failure (a lock that
                outlasts the busy timeout, corruption, an I/O error). Reporting
                0 for those made ``migrate_to_latest()`` treat an existing,
                older database as fresh and stamp it with the latest version
                without running a migration or taking a backup (#5597).
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
        except OperationalError as e:
            if _MISSING_VERSION_TABLE not in str(e.orig):
                logger.error(f"Could not read the schema version: {e}")
                raise
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
