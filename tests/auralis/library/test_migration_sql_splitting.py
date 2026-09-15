"""
Migration scripts are split where SQLite ends a statement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

apply_migration_sql split each script with ``sql.split(';')``. The header
comment of migration_v018_to_v019.sql (#5457) contains a semicolon ("...always
has; this repairs..."), so the text after it ran as a statement and failed with
``near "this": syntax error``. Every library at v18 therefore failed to start
(the backend answered 503). The #5457 test applied the script with
``executescript``, whose own parser skips comments, so it never saw the
production splitter.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import auralis.library
from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import (
    MigrationManager,
    check_and_migrate_database,
)
from auralis.library.migration_steps import split_sql_statements
from auralis.library.models import SchemaVersion

MIGRATIONS = Path(auralis.library.__file__).parent / "migrations"
_SQL_START = re.compile(
    r"^(CREATE|ALTER|UPDATE|INSERT|DELETE|DROP|PRAGMA|BEGIN|COMMIT|REPLACE|WITH)\b", re.IGNORECASE
)


def _code(statement: str) -> str:
    return "\n".join(
        line for line in statement.splitlines()
        if line.strip() and not line.lstrip().startswith("--")
    ).strip()


def test_a_semicolon_in_a_comment_does_not_end_a_statement():
    sql = (
        "-- header; this is still a comment\n"
        "UPDATE albums SET artist_id = 1\n"
        "WHERE artist_id IS NULL;\n"
        "-- trailing note; also a comment\n"
    )

    statements = split_sql_statements(sql)

    assert [_code(s) for s in statements] == [
        "UPDATE albums SET artist_id = 1\nWHERE artist_id IS NULL;"
    ]


def test_a_trigger_body_stays_one_statement():
    sql = (
        "CREATE TRIGGER t AFTER INSERT ON a BEGIN\n"
        "  UPDATE b SET n = n + 1;\n"
        "  UPDATE c SET n = n + 1;\n"
        "END;\n"
        "CREATE INDEX i ON a(x);\n"
    )

    assert len(split_sql_statements(sql)) == 2


@pytest.mark.parametrize(
    "path", sorted(MIGRATIONS.glob("migration_v*.sql")), ids=lambda p: p.name
)
def test_every_shipped_migration_splits_into_real_statements(path):
    for statement in split_sql_statements(path.read_text()):
        code = _code(statement)
        assert _SQL_START.match(code), f"{path.name} produced a non-SQL fragment: {code[:80]!r}"


def test_a_v018_library_migrates_to_the_current_version(tmp_path):
    """The exact path that failed for real libraries at v18."""
    db = tmp_path / "library.db"
    manager = MigrationManager(str(db))
    manager.initialize_fresh_database()
    manager.close()

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(SchemaVersion.__table__.delete())
        conn.execute(
            SchemaVersion.__table__.insert(),
            {"version": 18, "description": "v18 library", "migration_script": "test"},
        )
    engine.dispose()

    assert check_and_migrate_database(str(db), auto_backup=False) is True

    manager = MigrationManager(str(db))
    try:
        assert manager.get_current_version() == __db_schema_version__
    finally:
        manager.close()
