"""
Database migrations for Auralis library.

This package contains:
- SQL migration files (migration_vXXX_to_vYYY.sql)
- Python migration scripts for data transformations

The main migration logic (MigrationManager, check_and_migrate_database)
is in migration_manager.py at the parent level.
"""

# Re-export from parent migration_manager.py for backward compatibility.
# `backup_database` was omitted here even though it lives alongside the other
# two, so `from auralis.library.migrations import backup_database` — which
# tests/validation/validate_version_system.py does — raised ImportError.
from auralis.library.migration_manager import (
    MigrationManager,
    backup_database,
    check_and_migrate_database,
)

__all__ = ['MigrationManager', 'backup_database', 'check_and_migrate_database']
