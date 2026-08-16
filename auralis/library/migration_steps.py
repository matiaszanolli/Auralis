"""
Auralis Migration Step Execution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Locating, validating and atomically applying one version-step migration
script.

Split out of ``MigrationManager.apply_migration`` (#4511); the method is now a
thin delegation to ``run_migration_step``.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['run_migration_step', 'validate_migration_sql', 'apply_migration_sql']


def run_migration_step(
    engine: Any,
    migrations_dir: Path,
    from_version: int,
    to_version: int,
    now: Callable[[], Any],
) -> bool:
    """
    Apply migration from one version to another.

    Args:
        engine: SQLAlchemy engine bound to the database being migrated
        migrations_dir: Directory holding the versioned .sql scripts
        from_version: Current version
        to_version: Target version
        now: Timestamp factory for the ``applied_at`` column (see
            ``apply_migration_sql``)

    Returns:
        True if successful, False otherwise
    """
    migration_file = f"migration_v{from_version:03d}_to_v{to_version:03d}.sql"
    migration_path = migrations_dir / migration_file

    if not migration_path.exists():
        logger.error(f"Migration script not found: {migration_file}")
        return False

    logger.info(f"Applying migration: {migration_file}")

    try:
        # Read migration SQL
        with open(migration_path) as f:
            sql = f.read()

        if not validate_migration_sql(sql, migration_file):
            return False

        description = f"Migrated from v{from_version} to v{to_version}"

        apply_migration_sql(engine, sql, to_version, description, migration_file, now)

        logger.info(f"✅ Recorded migration to v{to_version}: {description}")
        logger.info(f"✅ Migration to v{to_version} completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def validate_migration_sql(sql: str, migration_file: str) -> bool:
    """
    Validate migration SQL before execution (#2083, #2925).

    Args:
        sql: Raw contents of the migration script
        migration_file: Script filename, used in the error messages

    Returns:
        True if the script is safe to execute, False otherwise
    """
    # DROP TABLE is normally rejected, but the SQLite recreate-and-copy
    # idiom (the only way to add a UNIQUE/PRIMARY KEY constraint to an
    # existing table) requires it. Migrations that genuinely need DROP
    # TABLE must declare `-- @ALLOW_DROP_TABLE` so the intent is
    # explicit and auditable in the migration file itself.
    sql_upper = sql.upper()
    allow_drop_table = '@ALLOW_DROP_TABLE' in sql_upper
    _DANGEROUS_KEYWORDS = {'DROP DATABASE'}
    if not allow_drop_table:
        _DANGEROUS_KEYWORDS = _DANGEROUS_KEYWORDS | {'DROP TABLE'}
    for keyword in _DANGEROUS_KEYWORDS:
        if keyword in sql_upper:
            logger.error(f"Migration {migration_file} contains dangerous operation: {keyword}")
            return False

    # Block unqualified DELETE FROM (no WHERE clause) — intentional
    # data wipes.  DELETE FROM ... WHERE ... is allowed (#2925).
    #
    # NOT re.MULTILINE: with it, `$` matched end-of-line, so a valid
    # multi-line `DELETE FROM t\nWHERE ...` was wrongly flagged as
    # unqualified because the newline after the table name satisfied
    # `$` before the WHERE on the next line. End-of-string `$` only.
    if re.search(r'DELETE\s+FROM\s+\w+\s*(;|$)', sql_upper):
        logger.error(f"Migration {migration_file} contains unqualified DELETE FROM (missing WHERE clause)")
        return False

    return True


def apply_migration_sql(
    engine: Any,
    sql: str,
    to_version: int,
    description: str,
    migration_file: str,
    now: Callable[[], Any],
) -> None:
    """
    Execute DDL and record version in the SAME transaction (#2905).

    Python's sqlite3 driver implicitly commits before DDL statements
    unless isolation_level is None (manual transaction control).  We
    drop to the raw DBAPI connection so BEGIN/COMMIT/ROLLBACK are
    fully under our control and DDL + version INSERT are truly atomic.

    ``now`` is injected rather than imported so the timestamp is produced by
    the caller's ``datetime`` — the atomicity regression test patches
    ``migration_manager.datetime`` to raise here, between the DDL and the
    version INSERT, and must keep hitting that exact point.
    """
    raw_conn = engine.raw_connection()
    try:
        dbapi_conn = raw_conn.dbapi_connection
        old_isolation = dbapi_conn.isolation_level
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("BEGIN")

            # Apply DDL statements
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for statement in statements:
                if statement:
                    try:
                        cursor.execute(statement)
                    except Exception as stmt_err:
                        # Tolerate "duplicate column" errors from ADD COLUMN
                        # on databases where the column was added outside
                        # the migration system.
                        if "duplicate column" in str(stmt_err).lower():
                            logger.warning(
                                f"Column already exists, skipping: {statement[:80]}"
                            )
                        else:
                            raise

            # Record the migration in the same transaction
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at, description, migration_script) "
                "VALUES (?, ?, ?, ?)",
                (to_version, now().isoformat(), description, migration_file),
            )

            cursor.execute("COMMIT")
        except BaseException:
            cursor.execute("ROLLBACK")
            raise
        finally:
            cursor.close()
            dbapi_conn.isolation_level = old_isolation
    finally:
        raw_conn.close()
