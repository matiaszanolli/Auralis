"""
Database migrations for Auralis library.

This package contains:
- SQL migration files (migration_vXXX_to_vYYY.sql)
- Python migration scripts for data transformations, run as modules
  (e.g. ``python -m auralis.library.migrations.normalize_existing_artists``)

The migration logic (MigrationManager, check_and_migrate_database,
backup_database) lives in ``auralis.library.migration_manager``; import it from
there. This package used to re-export those names "for backward
compatibility", but its only importer was a validation script deleted with the
never-collected tests/validation tree (#5149), so the re-export went too
(#5427).
"""
