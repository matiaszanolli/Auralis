"""
Pre-migration backup step
~~~~~~~~~~~~~~~~~~~~~~~~~

The "back up before migrating" step of ``check_and_migrate_database`` (#5839),
kept apart from the migration driver so that function reads as guard clauses.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from .migration_backup import backup_database

logger = logging.getLogger(__name__)


def backup_before_migration(db_path: str) -> tuple[bool, str | None]:
    """Back the database up ahead of a migration: ``(ok, backup_path)``.

    A failed backup aborts the migration (the caller returns False): migrating
    without a restore point is worse than not migrating.
    """
    try:
        # backup_database() already logs "✅ Database backed up" at INFO; the
        # path itself stays at DEBUG only (#4929).
        backup_path = backup_database(db_path)
        logger.debug(f"Pre-migration backup location: {backup_path}")
        return True, backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        logger.error("❌ Aborting migration - backup failed")
        return False, None
