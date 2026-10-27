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
        """Current schema version; 0 if there is no version table or row (fresh database).

        Any other read failure raises: reading it as 0 made ``migrate_to_latest()``
        stamp an older database with the latest version, unmigrated and
        unbacked-up (#5597).
        """
        try:
            with self._get_session() as session:
                result = session.execute(
                    select(SchemaVersion).order_by(SchemaVersion.version.desc())
                ).scalars().first()
                return int(result.version) if result else 0  # no row: fresh database
        except OperationalError as e:
            if _MISSING_VERSION_TABLE not in str(e.orig):
                raise
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
