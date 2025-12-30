"""
Database migrations for Auralis library.

This package contains:
- SQL migration files (migration_vXXX_to_vYYY.sql)
- Python migration scripts for data transformations

The main migration logic (MigrationManager, check_and_migrate_database)
is in migration_manager.py at the parent level.
"""

# Re-export from parent migration_manager.py for backward compatibility
from auralis.library.migration_manager import (
    MigrationManager,
    check_and_migrate_database,
)

__all__ = ['MigrationManager', 'check_and_migrate_database']
